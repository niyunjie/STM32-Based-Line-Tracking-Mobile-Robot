#include "global_state.h"

volatile CarMode_t g_CarMode = MODE_AUTO;
volatile CarState_t g_CarState = STATE_STOPPED;
volatile CarDirection_t g_CarDirection = DIR_STOP;

// === 修复点：补回丢失的速度变量初始化 ===
volatile int g_SpeedL = 0;
volatile int g_SpeedR = 0;

volatile float g_Distance = 0.0f;
volatile uint8_t g_StationCount = 0;
volatile uint32_t g_StationTimer = 0;

volatile int g_SetRunSpeed = 300; 
volatile int g_SetStopTime = 10;