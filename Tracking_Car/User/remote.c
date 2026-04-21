#include "remote.h"
#include "dma.h"
#include "motor.h"
#include "global_state.h"
#include "hcsr04.h" 
#include <stdio.h>
#include <math.h>
#include <stdlib.h>

#define RX_BUF_SIZE 64
volatile uint8_t rx_buffer[RX_BUF_SIZE];
static float desired_speed_L = 0;
static float desired_speed_R = 0;
static uint32_t last_send_time = 0;
static uint32_t last_sonar_tick = 0; 

extern DMA_HandleTypeDef hdma_usart1_rx;

void Remote_Init(void) {
    HAL_UARTEx_ReceiveToIdle_DMA(&huart1, (uint8_t *)rx_buffer, RX_BUF_SIZE);
    __HAL_DMA_DISABLE_IT(&hdma_usart1_rx, DMA_IT_HT);
}

static void Calculate_DiffDrive_Speed(int8_t x, int8_t y) {
    if (abs(x) < 10) x = 0; if (abs(y) < 10) y = 0;
    float nx = (float)x/100.0f; float ny = (float)y/100.0f;
    float sl = ny + nx; float sr = ny - nx;
    float maxv = fmax(fabs(sl), fabs(sr));
    if (maxv > 1.0f) { sl /= maxv; sr /= maxv; }
    desired_speed_L = sl; desired_speed_R = sr;
}

void Remote_UART_EventCallback(UART_HandleTypeDef *huart, uint16_t Size) {
    if (huart->Instance == USART1) {
        for (int i = 0; i <= Size - 6; i++) {
            // 遥控指令校验
            if (rx_buffer[i] == 0xA5 && rx_buffer[i+5] == 0x5A) {
                uint8_t sum = (uint8_t)rx_buffer[i+1] + (uint8_t)rx_buffer[i+2] + rx_buffer[i+3];
                if (sum == rx_buffer[i+4]) {
                    int8_t x = (int8_t)rx_buffer[i+1];
                    int8_t y = (int8_t)rx_buffer[i+2];
                    if (rx_buffer[i+3] == 1) { 
                        g_CarMode = MODE_MANUAL; 
                        Calculate_DiffDrive_Speed(x, y);
                    } else { g_CarMode = MODE_AUTO; }
                    break;
                }
            }
            // 参数设置校验
            else if (rx_buffer[i] == 0xB5 && rx_buffer[i+5] == 0x5B) {
                uint8_t spd = rx_buffer[i+1]; uint8_t tim = rx_buffer[i+2]; 
                uint8_t sum = spd + tim + rx_buffer[i+3];
                if (sum == rx_buffer[i+4]) {
                    if (spd > 100) spd = 100;
                    g_SetRunSpeed = spd * 10; g_SetStopTime = tim;
                    break;
                }
            }
        }
        HAL_UARTEx_ReceiveToIdle_DMA(&huart1, (uint8_t *)rx_buffer, RX_BUF_SIZE);
        __HAL_DMA_DISABLE_IT(&hdma_usart1_rx, DMA_IT_HT);
    }
}

void Remote_SendTelemetry(void) {
    if (HAL_GetTick() - last_send_time < 50) return; 
    last_send_time = HAL_GetTick();

    uint8_t tx[8];
    uint8_t st = (uint8_t)g_CarState;
    uint8_t dir = (uint8_t)g_CarDirection;
    
    // 【关键】计算速度位 (供上位机显示 快/慢)
    // 阈值设为 500 (对应上位机滑块 50%)
    uint8_t spd_lv = (g_SetRunSpeed > 500) ? 1 : 0; 
    
    uint8_t sta = g_StationCount;
    uint8_t dat = 0;

    if (g_CarState == STATE_STATION) {
        uint32_t elap = HAL_GetTick() - g_StationTimer;
        int rem = g_SetStopTime - (int)(elap/1000);
        if (rem < 0) rem = 0;
        dat = (uint8_t)rem;
    } else {
        int d = (int)g_Distance;
        if (d > 255) d = 255;
        dat = (uint8_t)d;
    }

    tx[0] = 0x55; tx[1] = st; tx[2] = dir; tx[3] = spd_lv;
    tx[4] = sta;  tx[5] = dat;
    tx[6] = (uint8_t)(st + dir + spd_lv + sta + dat);
    tx[7] = 0xAA;
    
    HAL_UART_Transmit(&huart1, tx, 8, 10);
}

void Remote_ManualLoop(void) {
    if (HAL_GetTick() - last_sonar_tick > 60) {
        HCSR04_Read(); last_sonar_tick = HAL_GetTick();
    }

    float limit = (float)g_SetRunSpeed;
    if (limit < 300) limit = 300;
    int pL = (int)(desired_speed_L * limit);
    int pR = (int)(desired_speed_R * limit);
    uint8_t is_AEB_Active = 0;

    if (g_Distance < 15.0f && g_Distance > 1.0f) {
        if (pL > 0) pL = 0;
        if (pR > 0) pR = 0;
        if (desired_speed_L > 0.1f || desired_speed_R > 0.1f) is_AEB_Active = 1;
    }

    Motor_SetSpeed(pL, pR);

    if (is_AEB_Active) {
        g_CarState = STATE_OBSTACLE; 
        g_CarDirection = DIR_STOP;
    } else if (abs(pL) < 50 && abs(pR) < 50) {
        g_CarState = STATE_STOPPED; g_CarDirection = DIR_STOP;
    } else {
        g_CarState = STATE_RUNNING;
        if (pL > pR + 50) g_CarDirection = DIR_RIGHT;
        else if (pR > pL + 50) g_CarDirection = DIR_LEFT;
        else if (pL > 0) g_CarDirection = DIR_FORWARD;
        else g_CarDirection = DIR_BACKWARD;
    }
    HAL_Delay(5);
}