#include "motor.h"
#include "tim.h" 
#include "global_state.h"

void Motor_Init(void)
{
    HAL_TIM_PWM_Start(&htim2, TIM_CHANNEL_1);
    HAL_TIM_PWM_Start(&htim2, TIM_CHANNEL_2);
    Motor_SetSpeed(0, 0);
}

// 在 motor.c 中
void Motor_SetSpeed(int speed_L, int speed_R)
{
    g_SpeedL = speed_L;
    g_SpeedR = speed_R;

    // --- 左轮逻辑 (保持不变，因为它是对的) ---
    if (speed_L >= 0) {
        HAL_GPIO_WritePin(GPIOA, GPIO_PIN_2, GPIO_PIN_SET);
        HAL_GPIO_WritePin(GPIOA, GPIO_PIN_3, GPIO_PIN_RESET);
    } else {
        HAL_GPIO_WritePin(GPIOA, GPIO_PIN_2, GPIO_PIN_RESET);
        HAL_GPIO_WritePin(GPIOA, GPIO_PIN_3, GPIO_PIN_SET);
        speed_L = -speed_L;
    }
    if(speed_L > 999) speed_L = 999;
    __HAL_TIM_SET_COMPARE(&htim2, TIM_CHANNEL_1, speed_L);

    // --- 右轮逻辑 (这里修改：反转 GPIO 电平) ---
    // 之前: >=0 是 Set/Reset。现在改为: Reset/Set，让它反向。
    if (speed_R >= 0) {
        // [修改点 1]: 正转逻辑反向
        HAL_GPIO_WritePin(GPIOA, GPIO_PIN_4, GPIO_PIN_RESET); // 原来是 SET
        HAL_GPIO_WritePin(GPIOA, GPIO_PIN_5, GPIO_PIN_SET);   // 原来是 RESET
    } else {
        // [修改点 2]: 反转逻辑反向
        HAL_GPIO_WritePin(GPIOA, GPIO_PIN_4, GPIO_PIN_SET);   // 原来是 RESET
        HAL_GPIO_WritePin(GPIOA, GPIO_PIN_5, GPIO_PIN_RESET); // 原来是 SET
        speed_R = -speed_R;
    }
    
    if(speed_R > 999) speed_R = 999;
    __HAL_TIM_SET_COMPARE(&htim2, TIM_CHANNEL_2, speed_R);
}