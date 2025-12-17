
# 微操Bot系统 - 多地图适配版本

## 系统概述

本系统包含多个微操Bot脚本，分别适配不同的地图和单位配置。所有Bot都专注于微操控制，不进行生产建造。

## 文件结构

### 核心运行脚本
- **`run_pvt_map.py`**: Protoss vs Terran 微操Bot
- **`run_zvt_map.py`**: Zerg vs Terran 基础微操Bot  
- **`run_zvt_2_map.py`**: Zerg vs Terran 增强微操Bot
- **`unit_count_bot.py`**: 单位统计Bot - 读取地图初始单位配置

### 地图文件
- **地图位置**: `auto-smac\Maps\simple_battle_maps\final_maps\`
- **适配地图**: `flat_test_final`, `flat_test_2_final`, `flat_test_3_final`, `flat_test_4_final`

## 脚本适配说明

### 1. run_pvt_map.py - Protoss vs Terran
**适配地图**: `flat_test_final`, `flat_test_2_final`, `flat_test_3_final`

**我方单位**: Zealot, Stalker, Colossus, High Templar, Archon, Disruptor
**敌方单位**: Marine, Marauder, Medivac, Ghost, Viking, Siege Tank, Liberator

**核心策略**:
- **Zealot**: 永远向前冲锋，使用冲锋技能
- **Stalker**: 护盾被打完后闪烁撤退，优先攻击空中单位
- **Colossus**: 专门攻击Marine和Marauder制造AOE伤害
- **High Templar**: Feedback反馈Ghost，释放心灵风暴，能量不足时合成执政官
- **Archon**: 前线坦克，吸收伤害
- **Disruptor**: 净化新星制造AOE伤害，专门打小型单位

### 2. run_zvt_map.py - Zerg vs Terran 基础版
**适配地图**: `flat_test_4_final`

**我方单位**: Zergling, Baneling, Ultralisk, Corruptor, Viper, Infestor
**敌方单位**: Marine, Marauder, Medivac, Ghost, Siege Tank, Liberator

**核心策略**:
- **Zergling**: 弧形进攻，包围敌人
- **Baneling**: 专门炸Marine密集区域，避免浪费
- **Ultralisk**: 前线坦克，冲击敌方阵型
- **Corruptor**: 专门对付空中单位，优先Liberator和Medivac
- **Viper**: 对坦克使用致盲云雾，对已架好的Liberator使用绑架
- **Infestor**: 真菌感染控制敌人，神经寄生重要单位

### 3. run_zvt_2_map.py - Zerg vs Terran 增强版
**适配地图**: `flat_test_4_final`

**我方单位**: Zergling, Baneling, Hydralisk, Broodlord, Infestor, Viper
**敌方单位**: Marine, Marauder, Helliontank, Ghost, Thor, Medivac, Siegetank

**核心策略**:
- **Ultralisk**: 大龙突击指定位置，优先攻击高威胁目标
- **Broodlord**: 远程重炮，优先攻击Thor和Helliontank
- **Hydralisk**: 远程支援和对空，优先攻击Medivac
- **Zergling**: 快速近战突击，包围战术
- **Infestor**: 真菌感染Ghost优先级，神经寄生Thor
- **Viper**: 对Thor集群使用致盲云雾，绑架关键目标

## 单位统计Bot - unit_count_bot.py

### 功能说明
`unit_count_bot.py` 是一个专门用于分析微操地图初始单位配置的工具Bot。

**主要功能**:
1. **初始单位扫描**: 游戏开始时自动扫描敌我双方单位配置
2. **详细统计**: 统计每种单位的数量、位置、血量、护盾等信息
3. **配置保存**: 将初始配置保存到JSON文件
4. **基本微操**: 扫描完成后进行基本的微操控制

**输出信息**:
- 我方单位配置统计
- 敌方单位配置统计  
- 详细单位位置和状态信息
- 单位配置JSON文件保存

**使用方法**:
```python
python unit_count_bot.py
```

## 运行方式

### 基础运行
```python
# PVT微操
python run_pvt_map.py

# ZVT基础微操  
python run_zvt_map.py

# ZVT增强微操
python run_zvt_2_map.py

# 单位统计
python unit_count_bot.py
```

### 自定义运行

注意realtime 在测试的时候可以设置为False， fullscreen可以设置为False
```python
def main():
    try:
        # 选择地图和Bot
        run_game(maps.get("flat_test_final"), [
            Human(Race.Terran), 
            Bot(Race.Protoss, ProtossBot())
        ], realtime=True) 
    except Exception as e:
        print(f"Game ended with exception: {e}")
        pass
```

## 技术特性

### 微操优化
1. **智能撤退**: 只有Viper和Infestor会撤退，其他单位弧形进攻
2. **技能优先级**: 蝰蛇优先对坦克使用致盲云雾，对Liberator使用绑架
3. **AOE躲避**: 考虑地雷和坦克AOE的躲避策略
4. **单位协同**: 不同单位类型之间的战术配合

### 地图适配
- 支持多种地图配置
- 自动识别单位类型和数量
- 根据地图特点调整战术策略

## 整合到课程学习

将LLM撰写的代码作为Bot传入运行脚本中：

```python
# 替换Human为对应的Bot类
[Bot(Race.Terran, TerranBot()), Bot(Race.Protoss, ProtossBot())]
```

其中左侧为player1，右侧为player2，只需要把Human替换为对应的Bot类即可。

