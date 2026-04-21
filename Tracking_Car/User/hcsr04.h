#ifndef __HCSR04_H__
#define __HCSR04_H__
#include "main.h"

void HCSR04_Init(void);
float HCSR04_Read(void);
void HCSR04_TimIC_Callback(TIM_HandleTypeDef *htim);

#endif

