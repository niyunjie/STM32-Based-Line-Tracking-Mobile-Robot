#include "tracker.h"
#include "motor.h"
#include "hcsr04.h"
#include "global_state.h"
#include "remote.h"
#include <stdlib.h> 
#include <math.h>

// === 引用全局配置变量 (由 remote.c 修改) ===
extern volatile int g_SetRunSpeed; 
extern volatile int g_SetStopTime;

// 硬件引脚
#define SENSOR_PORT GPIOB
#define S1_PIN GPIO_PIN_12 
#define S2_PIN GPIO_PIN_15 
#define S3_PIN GPIO_PIN_14 
#define S4_PIN GPIO_PIN_13 
#define S5_PIN GPIO_PIN_11 
#define BLACK_VAL 1 

// 参数 (宏定义中删除了速度和时间，改用变量)
#define TURN_SENSITIVITY 25     
#define STATION_JUDGE_TIME  180   
#define STATION_EXIT_TIME   400   
#define OBSTACLE_DIST 15.0f     
#define OBSTACLE_FILTER_NUM 3   
#define ARC_INIT_TURN_TIME   450   
#define ARC_OUTER_SPEED      250   
#define ARC_INNER_SPEED      130   
#define ARC_MAX_TIME         4000  

// 全局变量
static int last_error = 0; 
static uint32_t last_sonar_tick = 0;
static uint32_t last_avoid_end_time = 0; 
static int obstacle_valid_count = 0; 
static uint32_t station_start_tick = 0; 

void Tracker_Init(void){ 
    last_error = 0; last_sonar_tick = 0; 
    last_avoid_end_time = HAL_GetTick(); 
    station_start_tick = 0; obstacle_valid_count = 0;
}

static uint8_t Read_Sensor(uint16_t pin){
    return (HAL_GPIO_ReadPin(SENSOR_PORT, pin) == BLACK_VAL) ? 1 : 0;
}

// 避障逻辑
void Avoid_Obstacle_Routine(void) {
    g_CarState = STATE_OBSTACLE;
    Motor_SetSpeed(0, 0); HAL_Delay(200); 
    Motor_SetSpeed(-180, 180); HAL_Delay(ARC_INIT_TURN_TIME);
    Motor_SetSpeed(ARC_OUTER_SPEED, ARC_INNER_SPEED); 
    HAL_Delay(350); 

    uint32_t search_start = HAL_GetTick();
    while (HAL_GetTick() - search_start < ARC_MAX_TIME) {
        if (Read_Sensor(S1_PIN) || Read_Sensor(S2_PIN) || Read_Sensor(S3_PIN) || 
            Read_Sensor(S4_PIN) || Read_Sensor(S5_PIN)) {
            Motor_SetSpeed(-150, -150); HAL_Delay(100); 
            break; 
        }
    }
    g_Distance = 100.0f; obstacle_valid_count = 0;
    last_avoid_end_time = HAL_GetTick();
    g_CarState = STATE_RUNNING;
}

// ==========================================
// === 站点停车逻辑 (最终确认版) ===
// ==========================================
void Station_Routine(void)
{
    g_CarState = STATE_STATION;
    g_StationTimer = HAL_GetTick(); 
    
    // 1. 计数加1 (触发上位机记录)
    g_StationCount++; 
    
    // 2. 停车
    Motor_SetSpeed(0, 0);
    
    // 3. 非阻塞等待 (关键！保证上位机能收到数据)
    uint32_t wait_ms = g_SetStopTime * 1000;
    if (wait_ms < 1000) wait_ms = 1000; 

    while (HAL_GetTick() - g_StationTimer < wait_ms)
    {
        Remote_SendTelemetry(); // 持续心跳
        HAL_Delay(20);
    }

    g_CarState = STATE_RUNNING;
    
    // 4. 出站 (使用设定速度)
    Motor_SetSpeed(g_SetRunSpeed, g_SetRunSpeed); 
    HAL_Delay(STATION_EXIT_TIME); 
    station_start_tick = 0;
}

void Tracker_Loop(void)
{
    // 超声波避障
    if (HAL_GetTick() - last_avoid_end_time > 2000) {
        if (HAL_GetTick() - last_sonar_tick > 30) {
            HCSR04_Read(); last_sonar_tick = HAL_GetTick();
            float d = g_Distance;
            if (d < OBSTACLE_DIST && d > 1.0f) obstacle_valid_count++;
            else obstacle_valid_count = 0; 
        }
        if (obstacle_valid_count >= OBSTACLE_FILTER_NUM) {
            obstacle_valid_count = 0; Avoid_Obstacle_Routine(); return; 
        } 
    }
    if (g_CarState == STATE_OBSTACLE) g_CarState = STATE_RUNNING;

    // 传感器读取
    uint8_t s1 = Read_Sensor(S1_PIN); uint8_t s2 = Read_Sensor(S2_PIN); 
    uint8_t s3 = Read_Sensor(S3_PIN); uint8_t s4 = Read_Sensor(S4_PIN); 
    uint8_t s5 = Read_Sensor(S5_PIN); 
    int black_count = s1 + s2 + s3 + s4 + s5;

    // 站点判定
    if (black_count >= 3) {
        if (station_start_tick == 0) station_start_tick = HAL_GetTick();
        if (HAL_GetTick() - station_start_tick > STATION_JUDGE_TIME) {
            Station_Routine(); return; 
        }
    } else {
        station_start_tick = 0;
    }

    // PID 循迹
    int error = 0;
    if (black_count > 0) {
        if (s3) error = (s2)?-1:(s4?1:0);        
        else if (s2) error = (s1)?-3:-2;         
        else if (s4) error = (s5)?3:2;            
        else if (s1) error = -4; 
        else if (s5) error = 4;
        last_error = error; 
    } else {
        error = (last_error < 0) ? -5 : 5;                 
    }

    int turn_speed = error * TURN_SENSITIVITY;
    
    // 使用全局设定速度
    int current_base = g_SetRunSpeed;
    if (abs(error) >= 4) current_base = (int)(current_base * 0.7);

    Motor_SetSpeed(current_base + turn_speed, current_base - turn_speed);

    // 状态更新
    if (error == 0) g_CarDirection = DIR_FORWARD;
    else if (error < 0) g_CarDirection = DIR_LEFT;
    else g_CarDirection = DIR_RIGHT;
}