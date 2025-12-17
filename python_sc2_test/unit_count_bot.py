"""
微操地图单位统计Bot - 读取游戏开始时敌我双方单位种类数量
专门用于分析微操地图的初始单位配置
"""

from sc2 import maps
from sc2.data import Race
from sc2.main import run_game
from sc2.player import Bot, Human
from sc2.bot_ai import BotAI
from sc2.ids.unit_typeid import UnitTypeId
from collections import defaultdict
import json

class UnitCountBot(BotAI):
    """
    微操地图单位统计Bot
    功能：读取游戏开始时的单位配置，然后进行基本微操
    """

    def __init__(self):
        super().__init__()
        self.initial_scan_done = False
        self.our_unit_counts = defaultdict(int)
        self.enemy_unit_counts = defaultdict(int)

    async def on_step(self, iteration: int):
        """每一步的逻辑"""
        # 只在游戏开始时扫描一次
        if not self.initial_scan_done and iteration >= 1:
            await self.scan_initial_units()
            self.initial_scan_done = True

        # 扫描完成后进行基本微操
        if self.initial_scan_done:
            await self.basic_micro()

    async def scan_initial_units(self):
        """扫描游戏开始时的单位配置"""
        print("=" * 60)
        print("🔍 微操地图初始单位配置扫描")
        print("=" * 60)

        # 统计我方单位
        print("\n【我方单位配置】:")
        if self.units.exists:
            for unit in self.units:
                unit_name = unit.type_id.name
                self.our_unit_counts[unit_name] += 1

            # 按单位类型排序显示
            for unit_type, count in sorted(self.our_unit_counts.items()):
                print(f"  {unit_type}: {count} 个")

            our_total = sum(self.our_unit_counts.values())
            print(f"  总计: {our_total} 个单位")
        else:
            print("  无单位")

        # 统计敌方单位
        print("\n【敌方单位配置】:")
        if self.enemy_units.exists:
            for unit in self.enemy_units:
                unit_name = unit.type_id.name
                self.enemy_unit_counts[unit_name] += 1

            # 按单位类型排序显示
            for unit_type, count in sorted(self.enemy_unit_counts.items()):
                print(f"  {unit_type}: {count} 个")

            enemy_total = sum(self.enemy_unit_counts.values())
            print(f"  总计: {enemy_total} 个单位")
        else:
            print("  无单位")

        # 显示详细单位信息
        await self.show_detailed_unit_info()

        # 保存配置到文件
        await self.save_initial_config()

        print("\n" + "=" * 60)
        print("✅ 初始单位配置扫描完成，开始微操...")
        print("=" * 60)

    async def show_detailed_unit_info(self):
        """显示详细的单位信息"""
        print("\n【详细单位信息】:")

        # 我方单位详细信息
        if self.units.exists:
            print("\n我方单位位置和状态:")
            for i, unit in enumerate(self.units, 1):
                print(f"  {i}. {unit.type_id.name} - "
                      f"位置: ({unit.position.x:.1f}, {unit.position.y:.1f}) - "
                      f"血量: {unit.health}/{unit.health_max} - "
                      f"护盾: {unit.shield}/{unit.shield_max}")

        # 敌方单位详细信息
        if self.enemy_units.exists:
            print("\n敌方单位位置和状态:")
            for i, unit in enumerate(self.enemy_units, 1):
                print(f"  {i}. {unit.type_id.name} - "
                      f"位置: ({unit.position.x:.1f}, {unit.position.y:.1f}) - "
                      f"血量: {unit.health}/{unit.health_max} - "
                      f"护盾: {unit.shield}/{unit.shield_max}")

    async def save_initial_config(self):
        """保存初始配置到JSON文件"""
        config_data = {
            "map_name": "微操地图",
            "scan_time": self.time,
            "our_units": dict(self.our_unit_counts),
            "enemy_units": dict(self.enemy_unit_counts),
            "our_total": sum(self.our_unit_counts.values()),
            "enemy_total": sum(self.enemy_unit_counts.values()),
            "detailed_our_units": [],
            "detailed_enemy_units": []
        }

        # 添加详细单位信息
        for unit in self.units:
            config_data["detailed_our_units"].append({
                "type": unit.type_id.name,
                "position": {"x": unit.position.x, "y": unit.position.y},
                "health": unit.health,
                "health_max": unit.health_max,
                "shield": unit.shield,
                "shield_max": unit.shield_max
            })

        for unit in self.enemy_units:
            config_data["detailed_enemy_units"].append({
                "type": unit.type_id.name,
                "position": {"x": unit.position.x, "y": unit.position.y},
                "health": unit.health,
                "health_max": unit.health_max,
                "shield": unit.shield,
                "shield_max": unit.shield_max
            })

        # 保存到文件
        try:
            with open('micro_map_initial_config.json', 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
            print(f"\n💾 初始配置已保存到: micro_map_initial_config.json")
        except Exception as e:
            print(f"\n❌ 保存配置文件失败: {e}")

    async def basic_micro(self):
        """基本微操逻辑 - 简单的攻击指令"""
        if not self.units.exists or not self.enemy_units.exists:
            return

        # 让所有单位攻击最近的敌人
        for unit in self.units:
            if unit.is_idle:
                closest_enemy = self.enemy_units.closest_to(unit.position)
                unit.attack(closest_enemy)

    async def on_unit_destroyed(self, unit_tag):
        """单位被摧毁时的回调"""
        print(f"💥 单位被摧毁 (Tag: {unit_tag})")

    async def on_end(self, game_result):
        """游戏结束时的回调"""
        print(f"\n� 游戏结束，结果: {game_result}")
        print("感谢使用微操地图单位统计Bot!")


def main():
    """主函数"""
    try:
        print("🚀 启动微操地图单位统计Bot...")
        print("📍 地图: flat_test_final")
        print("⚔️  模式: 人类(Terran) vs Bot(Protoss)")
        print("🎯 功能: 读取初始单位配置 + 基本微操")
        print()

        run_game(
            maps.get("flat_test_5_final"),
            [Human(Race.Terran), Bot(Race.Protoss, UnitCountBot())],
            realtime=True
        )
    except Exception as e:
        print(f"\n⚠️  游戏结束: {e}")
        print("(这通常是正常的游戏结束信号)")
    finally:
        print("\n👋 微操地图单位统计Bot已结束")


if __name__ == "__main__":
    main()
