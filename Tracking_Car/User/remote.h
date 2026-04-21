#ifndef __REMOTE_H__
#define __REMOTE_H__
#include "main.h"
#include "usart.h"

void Remote_Init(void);
void Remote_UART_EventCallback(UART_HandleTypeDef *huart, uint16_t Size);
void Remote_ManualLoop(void);
void Remote_SendTelemetry(void); // 进阶功能：发送回传数据
#endif