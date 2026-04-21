#ifndef __GLOBAL_STATE_H__
#define __GLOBAL_STATE_H__

#include "main.h"

// 模式定义
typedef enum { MODE_AUTO = 0, MODE_MANUAL = 1 } CarMode_t;

// 运行状态定义
typedef enum { 
    STATE_STOPPED = 0,  // 停止
    STATE_RUNNING = 1,  // 正常行驶
    STATE_OBSTACLE = 2, // 避障停车
    STATE_STATION = 3   // 站点停靠中
} CarState_t;

// 方向定义
typedef enum {
    DIR_STOP, DIR_FORWARD, DIR_BACKWARD, DIR_LEFT, DIR_RIGHT
} CarDirection_t;

// 全局变量声明
extern volatile CarMode_t g_CarMode;
extern volatile CarState_t g_CarState;
extern volatile CarDirection_t g_CarDirection;

// === 修复点：补回丢失的速度变量 ===
extern volatile int g_SpeedL;
extern volatile int g_SpeedR;

extern volatile float g_Distance;       // 超声波距离
extern volatile uint8_t g_StationCount; // 站点计数
extern volatile uint32_t g_StationTimer;// 站点计时器

// 进阶参数
extern volatile int g_SetRunSpeed;
extern volatile int g_SetStopTime;

#endif