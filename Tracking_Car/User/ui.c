#include "ui.h"
#include "oled.h"
#include "global_state.h"
#include <stdio.h>

void UI_Init(void) { 
    HAL_Delay(100); 
    OLED_Init(); 
    OLED_NewFrame(); 
    OLED_ShowFrame(); 
}

void UI_Update(void) {
    char buf[32];
    OLED_NewFrame();

    // ============================================
    // Line 1 (Y=0): 状态 (RUN/STA) & 速度 (Fast/Slow)
    // ============================================
    char *st = "STOP";
    
    // 借用 STATE_OBSTACLE 作为手动模式下的 AEB 报警状态
    if (g_CarState == STATE_OBSTACLE && g_CarMode == MODE_MANUAL) {
        st = "!BRAKE!"; // 刹车警告
    } else if (g_CarState == STATE_RUNNING) {
        st = "RUN";
    } else if (g_CarState == STATE_STATION) {
        st = "STA";
    } else if (g_CarState == STATE_OBSTACLE) {
        st = "OBS";
    }
    
    char *spd = "Slow";
    if (g_SetRunSpeed > 600) spd = "Fast";
    if (g_CarState == STATE_STOPPED) spd = "Stop";
    
    // 显示格式: "RUN  Fast"
    sprintf(buf, "%s  %s", st, spd);
    OLED_PrintASCIIString(0, 0, buf, &afont16x8, OLED_COLOR_NORMAL);

    // ============================================
    // Line 2 (Y=20): 方向 (Dir) & 站点数 (Site)
    // ============================================
    char *dr = "--";
    switch(g_CarDirection) {
        case DIR_FORWARD:  dr = "FWD"; break;
        case DIR_BACKWARD: dr = "BWD"; break;
        case DIR_LEFT:     dr = "LFT"; break;
        case DIR_RIGHT:    dr = "RGT"; break;
        case DIR_STOP:     dr = "---"; break;
    }
    
    // 【修改点】在这里增加了站点显示
    // 显示格式: "Dir:FWD Site:1"
    sprintf(buf, "Dir:%s Site:%d", dr, g_StationCount);
    OLED_PrintASCIIString(0, 20, buf, &afont16x8, OLED_COLOR_NORMAL);

    // ============================================
    // Line 3 (Y=40): 倒计时 (Wait) 或 距离 (Dist)
    // ============================================
    if (g_CarState == STATE_STATION) {
        // 计算倒计时
        int rem = g_SetStopTime - (int)((HAL_GetTick() - g_StationTimer)/1000);
        if (rem < 0) rem = 0;
        
        // 显示倒计时: "Wait: 5s"
        sprintf(buf, "Wait: %ds", rem);
    } else {
        // 显示距离: "Dist: 15cm"
        sprintf(buf, "Dist: %.0fcm", g_Distance);
    }
    OLED_PrintASCIIString(0, 40, buf, &afont16x8, OLED_COLOR_NORMAL);

    // ============================================
    // Line 4 (Y=56): 视觉雷达条 (仅在非停靠时显示)
    // ============================================
    if (g_CarState != STATE_STATION) {
        // 画外框
        OLED_DrawRectangle(0, 56, 127, 7, OLED_COLOR_NORMAL);
        
        // 计算填充长度 (0-60cm 量程)
        int w = 0;
        if (g_Distance < 60.0f && g_Distance > 0.1f) {
            w = (int)((60.0f - g_Distance) / 60.0f * 123.0f);
        }
        if (w > 123) w = 123;
        
        // 填充进度条
        if (w > 0) {
            OLED_DrawFilledRectangle(2, 58, w, 3, OLED_COLOR_NORMAL);
        }
    }

    // ============================================
    // 特殊层: AEB 触发时的全屏弹窗警告
    // ============================================
    if (g_CarState == STATE_OBSTACLE && g_CarMode == MODE_MANUAL) {
        // 覆盖屏幕中间显示反色警告框
        OLED_DrawFilledRectangle(20, 18, 88, 20, OLED_COLOR_NORMAL); // 黑底擦除
        OLED_DrawRectangle(20, 18, 88, 20, OLED_COLOR_REVERSED);     // 白边框
        OLED_PrintASCIIString(35, 20, "BRAKE!", &afont16x8, OLED_COLOR_REVERSED); // 反色字
    }

    OLED_ShowFrame();
}