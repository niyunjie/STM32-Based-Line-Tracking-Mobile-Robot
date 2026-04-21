#include "hcsr04.h"
#include "tim.h"
#include "global_state.h"

#define TRIG_PORT GPIOA
#define TRIG_PIN  GPIO_PIN_11

static void delay_us(uint16_t us)
{
    uint16_t start_time = (uint16_t)__HAL_TIM_GET_COUNTER(&htim1);
    while((uint16_t)(__HAL_TIM_GET_COUNTER(&htim1) - start_time) < us);
}

// 内部函数声明
static void HCSR04_Trigger(void);

void HCSR04_Init(void)
{
    HAL_TIM_Base_Start(&htim1);
    HAL_TIM_IC_Start(&htim1, TIM_CHANNEL_3);
    HAL_TIM_IC_Start_IT(&htim1, TIM_CHANNEL_4);
    HAL_GPIO_WritePin(TRIG_PORT, TRIG_PIN, GPIO_PIN_RESET);
    g_Distance = 999.0f;
}

static void HCSR04_Trigger(void)
{
    HAL_GPIO_WritePin(TRIG_PORT, TRIG_PIN, GPIO_PIN_SET);
    delay_us(15);
    HAL_GPIO_WritePin(TRIG_PORT, TRIG_PIN, GPIO_PIN_RESET);
}

float HCSR04_Read(void)
{
    HCSR04_Trigger();
    return g_Distance;
}

void HCSR04_TimIC_Callback(TIM_HandleTypeDef *htim)
{
    if (htim->Instance == TIM1 && htim->Channel == HAL_TIM_ACTIVE_CHANNEL_4)
    {
        uint16_t StartVal = (uint16_t)HAL_TIM_ReadCapturedValue(htim, TIM_CHANNEL_3);
        uint16_t EndVal = (uint16_t)HAL_TIM_ReadCapturedValue(htim, TIM_CHANNEL_4);
        uint16_t pulse_width = EndVal - StartVal;

        float distance = (float)pulse_width / 58.3f;

        if (distance > 400.0f || distance < 1.0f) {
            // 过滤无效值
        } else {
            g_Distance = distance;
        }
    }
}
