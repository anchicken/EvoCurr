#!/usr/bin/env python3
"""
StormLib SC2 单位编辑器 - 改进版
基于 StormLib 实现对 SC2 地图中单位的添加和修改
新增：高度图提取和分析功能，生成更合理的单位放置位置
"""

import os
import ctypes
from ctypes import windll, wintypes
import tempfile
import shutil
import xml.etree.ElementTree as ET
import random
import json
import openai
import struct
import re
import numpy as np
from PIL import Image
import base64
import io
from datetime import datetime
from configs.rollout_config import scenario_type
from configs.rollout_config import map_name

class TerrainAnalyzer:
    """地形分析器 - 用于分析地图高度和可放置区域"""

    def __init__(self):
        self.height_map = None
        self.walkable_map = None
        self.map_width = 0
        self.map_height = 0
        self.height_scale = 1.0

    def parse_height_map(self, height_data):
        """解析高度图数据"""
        try:

            header_format = '<4sIII'  # 4s: 4字节字符串, I: uint32, f: float
            header_size = struct.calcsize(header_format)
            if len(height_data) < header_size:
                return False

            if len(height_data) >= header_size:
                magic, version, self.map_width, self.map_height = struct.unpack(
                    "<4sIII", height_data[:16]
                )

            expected_size = self.map_width * self.map_height * 2  # 每个高度值2字节

            if len(height_data) < 16 + expected_size:
                print(f"❌ 高度图数据不完整: 期望{expected_size}字节，实际{len(height_data) - 16}字节")
                return False

            # 解析高度数据
            height_raw = height_data[16:16 + expected_size]

            heights = struct.unpack(f'<{self.map_width * self.map_height}H', height_raw)

            # 转换为numpy数组
            self.height_map = np.array(heights, dtype=np.uint16).reshape(self.map_height, self.map_width)

            # 计算高度范围
            min_height = np.min(self.height_map)
            max_height = np.max(self.height_map)
            self.height_scale = (max_height - min_height) / 65535.0 if max_height > min_height else 1.0

            print(f"✅ 高度图解析成功: {self.map_width}x{self.map_height}, 高度范围: {min_height}-{max_height}")
            return True

        except Exception as e:
            print(f"❌ 高度图解析失败: {e}")
            return False

    def parse_pathing_map(self, pathing_data):
        """解析路径图数据（可行走区域）"""
        try:
            if len(pathing_data) < 16:
                return False

            # 读取路径图头部信息
            header = struct.unpack('<II', pathing_data[:16])

            width = header[0]
            height = header[1]

            if width != self.map_width or height != self.map_height:
                print(f"⚠️  路径图尺寸与高度图不匹配: {width}x{height} vs {self.map_width}x{self.map_height}")

            # 解析路径数据（每个点1字节）
            expected_size = width * height

            if len(pathing_data) < 16 + expected_size:
                print(f"❌ 路径图数据不完整")
                return False

            pathing_raw = pathing_data[16:16 + expected_size]

            pathing_values = struct.unpack(f'<{width * height}B', pathing_raw)

            # 转换为numpy数组
            self.walkable_map = np.array(pathing_values, dtype=np.uint8).reshape(height, width)

            walkable_count = np.sum(self.walkable_map > 0)
            total_count = width * height
            print(f"✅ 路径图解析成功: {walkable_count}/{total_count} 个可行走点 ({walkable_count / total_count * 100:.1f}%)")
            return True

        except Exception as e:
            print(f"❌ 路径图解析失败: {e}")
            return False

    def get_height_at_position(self, x, y):
        """获取指定位置的高度"""
        if self.height_map is None:
            return 0.0

        # 转换坐标到高度图坐标系
        map_x = int(x)
        map_y = int(y)

        if 0 <= map_x < self.map_width and 0 <= map_y < self.map_height:
            raw_height = self.height_map[map_y, map_x]
            # 转换为游戏中的高度值
            return float(raw_height) * self.height_scale

        return 0.0

    def is_position_walkable(self, x, y):
        """检查位置是否可行走"""
        if self.walkable_map is None:
            return True  # 如果没有路径图，假设可行走

        map_x = int(x)
        map_y = int(y)

        if 0 <= map_x < self.map_width and 0 <= map_y < self.map_height:
            return self.walkable_map[map_y, map_x] > 0

        return False

    def find_safe_positions(self, count, min_distance=3.0, avoid_edges=True):
        """寻找安全的放置位置"""
        safe_positions = []

        if self.height_map is None:
            # 如果没有高度图，使用0-31范围内的随机位置
            for _ in range(count):
                x = random.uniform(2, 29)
                y = random.uniform(2, 29)
                safe_positions.append((x, y, 0.0))
            return safe_positions

        # 强制限制边界为0-31
        margin = 2 if avoid_edges else 0
        min_x, max_x = margin, min(31 - margin, self.map_width)
        min_y, max_y = margin, min(31 - margin, self.map_height)

        # 计算高度梯度（用于避免陡峭区域）
        height_gradient = np.gradient(self.height_map.astype(float))
        gradient_magnitude = np.sqrt(height_gradient[0] ** 2 + height_gradient[1] ** 2)

        max_attempts = count * 50
        attempts = 0

        while len(safe_positions) < count and attempts < max_attempts:
            attempts += 1

            # 随机选择位置
            x = random.uniform(min_x, max_x)
            y = random.uniform(min_y, max_y)

            map_x, map_y = int(x), int(y)

            # 检查是否可行走
            if not self.is_position_walkable(x, y):
                continue

            # 检查坡度是否过陡
            if gradient_magnitude[map_y, map_x] > 200:  # 调整这个阈值
                continue

            # 检查与现有位置的距离
            too_close = False
            for existing_pos in safe_positions:
                dist = ((x - existing_pos[0]) ** 2 + (y - existing_pos[1]) ** 2) ** 0.5
                if dist < min_distance:
                    too_close = True
                    break

            if too_close:
                continue

            # 获取高度
            height = self.get_height_at_position(x, y)
            safe_positions.append((x, y, height))

        # 如果找不到足够的位置，用简单随机填充
        while len(safe_positions) < count:
            x = random.uniform(min_x, max_x)
            y = random.uniform(min_y, max_y)
            height = self.get_height_at_position(x, y)
            safe_positions.append((x, y, height))

        return safe_positions

    def get_terrain_summary(self):
        """获取地形摘要信息"""
        if self.height_map is None:
            return {
                "map_size": "unknown",
                "height_range": "unknown",
                "average_height": "unknown",
                "height_variation": "unknown",
                "walkable_ratio": "unknown",
                "terrain_type": "unknown"
            }

        heights = self.height_map.flatten()
        min_height = np.min(heights)
        max_height = np.max(heights)
        avg_height = np.mean(heights)
        height_std = np.std(heights)

        # 可行走区域比例
        walkable_ratio = 0.0
        if self.walkable_map is not None:
            walkable_ratio = np.sum(self.walkable_map > 0) / (self.map_width * self.map_height)

        summary = {
            "map_size": f"{self.map_width}x{self.map_height}",
            "height_range": f"{min_height}-{max_height}",
            "average_height": f"{avg_height:.1f}",
            "height_variation": f"{height_std:.1f}",
            "walkable_ratio": f"{walkable_ratio:.1%}",
            "terrain_type": "平坦" if height_std < 100 else "多山" if height_std > 500 else "丘陵"
        }
        return summary

    def create_height_map_image(self):
        """创建高度图的可视化图像"""
        if self.height_map is None:
            return None

        # 归一化高度图到0-255
        normalized = ((self.height_map - np.min(self.height_map)) /
                      (np.max(self.height_map) - np.min(self.height_map)) * 255).astype(np.uint8)

        # 创建PIL图像
        img = Image.fromarray(normalized, mode='L')

        # 如果图像太小，放大它
        if img.width < 200 or img.height < 200:
            scale = max(200 // img.width, 200 // img.height, 1)
            new_size = (img.width * scale, img.height * scale)
            img = img.resize(new_size, Image.NEAREST)

        return img

    def get_height_map_base64(self):
        """获取高度图的base64编码（用于LLM分析）"""
        img = self.create_height_map_image()
        if img is None:
            return None

        # 转换为base64
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        img_base64 = base64.b64encode(buffer.getvalue()).decode()

        return img_base64


class StormLibUnitEditor:
    """使用 StormLib 的 SC2 单位编辑器"""

    def __init__(self):
        """初始化 StormLib"""
        dll_path = r"..\stormlib_dll\x64\StormLib.dll"
        if not os.path.exists(dll_path):
            raise FileNotFoundError(f"StormLib.dll not found: {dll_path}")

        self.lib = windll.LoadLibrary(dll_path)
        self.terrain_analyzer = TerrainAnalyzer()
        self._setup_functions()
        print("✅ StormLib 单位编辑器初始化完成")

    def _setup_functions(self):
        """设置 StormLib 函数原型"""
        # 添加文件
        self.lib.SFileAddFileEx.argtypes = [
            wintypes.HANDLE, wintypes.LPCWSTR, ctypes.c_char_p,
            wintypes.DWORD, wintypes.DWORD, wintypes.DWORD
        ]
        self.lib.SFileAddFileEx.restype = wintypes.BOOL

        # 打开档案
        self.lib.SFileOpenArchive.argtypes = [
            wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)
        ]
        self.lib.SFileOpenArchive.restype = wintypes.BOOL

        # 文件操作
        self.lib.SFileOpenFileEx.argtypes = [
            wintypes.HANDLE, ctypes.c_char_p, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)
        ]
        self.lib.SFileOpenFileEx.restype = wintypes.BOOL

        self.lib.SFileGetFileSize.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        self.lib.SFileGetFileSize.restype = wintypes.DWORD

        self.lib.SFileReadFile.argtypes = [
            wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p
        ]
        self.lib.SFileReadFile.restype = wintypes.BOOL

        self.lib.SFileHasFile.argtypes = [wintypes.HANDLE, ctypes.c_char_p]
        self.lib.SFileHasFile.restype = wintypes.BOOL

        # 关闭操作
        self.lib.SFileCloseFile.argtypes = [wintypes.HANDLE]
        self.lib.SFileCloseFile.restype = wintypes.BOOL

        self.lib.SFileCloseArchive.argtypes = [wintypes.HANDLE]
        self.lib.SFileCloseArchive.restype = wintypes.BOOL

        self.lib.SFileCompactArchive.argtypes = [wintypes.HANDLE, wintypes.LPCWSTR, wintypes.BOOL]
        self.lib.SFileCompactArchive.restype = wintypes.BOOL

        # 错误处理
        self.get_last_error = windll.kernel32.GetLastError
        self.get_last_error.restype = wintypes.DWORD

    def analyze_map_terrain(self, map_path):
        """分析地图地形信息"""
        print(f"\n=== 分析地图地形: {os.path.basename(map_path)} ===")

        # 提取高度图
        height_data = self._extract_file_from_map(map_path, "t3HeightMap")
        if height_data:
            success = self.terrain_analyzer.parse_height_map(height_data)
            if not success:
                print("⚠️  高度图解析失败，将使用默认高度")
        else:
            print("⚠️  未找到高度图文件")

        # 输出地形摘要
        summary = self.terrain_analyzer.get_terrain_summary()
        print("📊 地形摘要:")
        for key, value in summary.items():
            print(f"  {key}: {value}")

        return self.terrain_analyzer

    def analyze_map_units(self, map_path):
        """分析地图中的单位"""
        print(f"\n=== 分析地图单位: {os.path.basename(map_path)} ===")

        try:
            # 提取 Objects 文件
            objects_data = self._extract_file_from_map(map_path, "Objects")
            if not objects_data:
                print("❌ 未找到 Objects 文件")
                return []

            # 解析单位数据
            units = self._parse_objects_xml(objects_data)

            if units:
                print(f"✅ 找到 {len(units)} 个单位:")
                unit_types = {}
                for unit in units:
                    unit_type = unit['type']
                    player = unit['player']
                    key = f"玩家{player}-{unit_type}"
                    unit_types[key] = unit_types.get(key, 0) + 1

                for key, count in unit_types.items():
                    print(f"  {key}: {count} 个")
            else:
                print("❌ 没有找到有效的单位数据")

            return units

        except Exception as e:
            print(f"❌ 地图分析失败: {e}")
            return []

    def generate_intelligent_battle_config(self, client, units_data, terrain_analyzer):
        """使用LLM生成智能的战斗配置"""

        # 准备地形信息 - 确保返回字典
        terrain_summary = terrain_analyzer.get_terrain_summary()
        if isinstance(terrain_summary, str):
            # 如果返回字符串，创建默认字典
            terrain_summary = {
                "map_size": "unknown",
                "height_range": "unknown",
                "terrain_type": "unknown",
                "walkable_ratio": "unknown"
            }

        # 获取安全位置示例
        try:
            sample_positions = terrain_analyzer.find_safe_positions(10, min_distance=5.0)
        except Exception as e:
            print(f"⚠️ 获取安全位置失败: {e}")
            sample_positions = [(10, 10, 0), (20, 20, 0), (30, 30, 0)]

        # 构建提示词 - 安全地访问字典项
        prompt_content = f"""
    基于以下SC2地图信息，设计一个合理的战斗场景配置：

    地形信息：
    - 地图尺寸: {terrain_summary.get('map_size', 'unknown')}
    - 高度范围: {terrain_summary.get('height_range', 'unknown')} 
    - 地形类型: {terrain_summary.get('terrain_type', 'unknown')}
    - 可行走区域比例: {terrain_summary.get('walkable_ratio', 'unknown')}

    可用单位类型：
    {json.dumps(list(units_data.keys())[:20] if isinstance(units_data, dict) else [], indent=2, ensure_ascii=False)}

    安全位置示例（已考虑地形和可行走性）：
    {sample_positions[:5]}

    请生成一个战斗配置，要求：
    1. 位置坐标必须在地图范围内,给出的x，y坐标需在0到31的范围内，z坐标需要根据x，y坐标以及高度图中对应的值给出
    2. 使用提供的安全位置或类似的坐标,不要生成悬崖或斜坡的地形的位置坐标
    3. 考虑地形特点安排单位
    4. 两个玩家的单位要有合理的距离
    5. 单位数量和类型要平衡

    返回格式必须严格按照以下JSON格式：
    ```json
    {{
    "scenario_type": "pvp",
    "clear_existing": true,
    "player1_units": [
        {{"type": "Marine", "count": 8, "position": [x, y, z]}}
    ],
    "player2_units": [
        {{"type": "Zealot", "count": 6, "position": [x, y, z]}}
    ]
    }}
    ```

    注意：position必须是[x, y, z]格式的数组，z值为高度。
    """

        try:
            response = client.chat.completions.create(
                model="deepseek-reasoner",
                messages=[{"role": "user", "content": prompt_content}]
            )

            response_text = response.choices[0].message.content
            print("🤖 LLM响应:")
            print(response_text[:500] + "..." if len(response_text) > 500 else response_text)

            # 提取JSON配置
            config = extract_json_robust(response_text)

            if config:
                # 验证和修正位置
                config = self._validate_and_fix_positions(config, terrain_analyzer)
                print("✅ 智能配置生成成功")
                return config
            else:
                print("❌ 无法解析LLM返回的配置")
                return None

        except Exception as e:
            print(f"❌ LLM配置生成失败: {e}")
            return None

    def _validate_and_fix_positions(self, config, terrain_analyzer):
        """验证和修正位置坐标"""
        print("🔍 验证和修正位置坐标...")

        for player_key in ['player1_units', 'player2_units']:
            if player_key not in config:
                continue

            for unit_config in config[player_key]:
                if 'position' not in unit_config:
                    continue

                pos = unit_config['position']
                if isinstance(pos, (list, tuple)) and len(pos) >= 2:
                    x, y = pos[0], pos[1]

                    # 强制限制坐标在0-31范围内
                    x = max(0, min(x, 31))
                    y = max(0, min(y, 31))

                    # 获取精确的高度
                    z = terrain_analyzer.get_height_at_position(x, y)

                    # 如果位置不可行走，寻找附近的安全位置
                    if not terrain_analyzer.is_position_walkable(x, y):
                        safe_positions = terrain_analyzer.find_safe_positions(1, min_distance=1.0)
                        if safe_positions:
                            safe_x, safe_y, safe_z = safe_positions[0]
                            # 确保安全位置也在范围内
                            x = max(0, min(safe_x, 31))
                            y = max(0, min(safe_y, 31))
                            z = safe_z

                    # 更新位置
                    unit_config['position'] = [x, y, z]
                    print(f"  修正位置: {unit_config['type']} -> ({x:.1f}, {y:.1f}, {z:.1f})")

        return config

    def modify_map_units(self, source_map_path, output_path, unit_modifications):
        """修改地图中的单位"""
        print(f"\n=== 修改地图单位: {os.path.basename(source_map_path)} -> {os.path.basename(output_path)} ===")

        try:
            # 1. 复制原地图
            shutil.copy2(source_map_path, output_path)
            print(f"📋 复制基础地图完成")

            # 2. 准备临时目录
            temp_dir = tempfile.mkdtemp(prefix="unit_modify_")
            print(f"📁 临时目录: {temp_dir}")

            # 3. 读取原有单位数据
            original_units = self._get_original_units(source_map_path)
            print(f"📊 原有单位数量: {len(original_units)}")

            # 4. 处理单位修改
            new_units = self._process_unit_modifications(original_units, unit_modifications)
            print(f"📊 修改后单位数量: {len(new_units)}")

            # 5. 生成新的 Objects 文件
            objects_xml = self._generate_objects_xml(new_units)
            objects_path = os.path.join(temp_dir, "Objects")
            with open(objects_path, 'w', encoding='utf-8') as f:
                f.write(objects_xml)
            modified_files = [('Objects', objects_path)]

            if unit_modifications.get('abilities'):
                  # 构造 Upgrades XML
                upgrades_root = ET.Element("Upgrades")

                for ab in unit_modifications['abilities']:
                    up = ET.SubElement(upgrades_root, "Upgrade")
                    up.set("Player", str(ab['player']))
                    up.set("UpgradeID", ab['upgrade_id'])
                    up.set("Level", str(ab['level']))
                upgrades_xml = ET.tostring(upgrades_root, encoding='utf-8', xml_declaration=True).decode()

                upgrades_path = os.path.join(temp_dir, "Upgrades")

                with open(upgrades_path, 'w', encoding='utf-8') as f:
                    f.write(upgrades_xml)
                modified_files.append(('Upgrades', upgrades_path))
            else:
                modified_files = [('Objects', objects_path)]


            # 6. 替换文件到地图

            success = self._replace_files_in_map(output_path, modified_files)

            if not success:
                raise Exception("文件替换失败")

            # 7. 清理临时文件
            shutil.rmtree(temp_dir)

            print(f"✅ 单位修改完成: {output_path}")
            return True

        except Exception as e:
            print(f"❌ 单位修改失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _get_original_units(self, map_path):
        """获取原有单位数据"""
        objects_data = self._extract_file_from_map(map_path, "Objects")
        if objects_data:
            return self._parse_objects_xml(objects_data)
        return []

    def _parse_objects_xml(self, objects_data):
        """解析 Objects XML 数据"""
        try:
            objects_xml = objects_data.decode('utf-8', errors='ignore')
            root = ET.fromstring(objects_xml)

            all_objects = []
            for obj_elem in root:
                obj_info = {"tag": obj_elem.tag, "attrib": dict(obj_elem.attrib)}

                if obj_elem.tag == "ObjectUnit":
                    obj_info.update({
                        'id': obj_elem.get('Id', ''),
                        'type': obj_elem.get('UnitType', ''),
                        'player': obj_elem.get('Player', '1'),
                        'position': obj_elem.get('Position', '0,0,0'),
                        'rotation': obj_elem.get('Rotation', '0'),
                        'scale': obj_elem.get('Scale', '1,1,1'),
                    })
                all_objects.append(obj_info)

            return all_objects
        except Exception as e:
            print(f"❌ XML 解析失败: {e}")
            return []

    def _process_unit_modifications(self, original_objects, modifications):
        """
        处理单位修改逻辑，兼容两种输入结构：
        1) 旧结构：列表仅包含单位字典（没有 'tag' 字段）
        2) 新结构：混合对象列表（非单位对象 + 单位对象，单位对象以 tag == 'ObjectUnit' 区分）

        返回结构与输入保持一致：如果输入是混合结构就返回混合结构；如果输入是仅单位，就返回仅单位。
        """
        # 判定输入结构
        is_mixed_schema = any(isinstance(obj, dict) and ('tag' in obj) for obj in original_objects)

        # 分离非单位对象与单位对象
        if is_mixed_schema:
            preserved_other = [obj for obj in original_objects if obj.get("tag") != "ObjectUnit"]
            original_units = [obj for obj in original_objects if obj.get("tag") == "ObjectUnit"]
        else:
            preserved_other = []  # 旧结构拿不到非单位对象
            original_units = list(original_objects)

        # 基础集合：是否清空现有单位
        if not modifications.get('clear_all', False):
            new_units = [u.copy() for u in original_units]
            print(f"📋 保留原有 {len(original_units)} 个单位")
        else:
            new_units = []
            print("🧹 清除所有原有单位")

        # 移除指定类型的单位
        if 'remove_units' in modifications:
            remove_types = set(modifications['remove_units'])
            before_count = len(new_units)
            new_units = [u for u in new_units if u.get('type') not in remove_types]
            removed_count = before_count - len(new_units)
            print(f"🗑️  移除了 {removed_count} 个单位 (类型: {list(remove_types)})")

        # 替换单位类型
        if 'replace_units' in modifications:
            replace_map = modifications['replace_units']
            replaced_count = 0
            for u in new_units:
                ut = u.get('type')
                if ut in replace_map:
                    u['type'] = replace_map[ut]
                    replaced_count += 1
            print(f"🔄 替换了 {replaced_count} 个单位类型")

        # 计算下一个可用ID（从现有对象里收集所有可解析的 id）
        def _to_int_id(v):
            try:
                return int(v)
            except Exception:
                return None

        existing_ids = []
        scan_pool = []
        if is_mixed_schema:
            scan_pool.extend(preserved_other)
        scan_pool.extend(new_units)

        for obj in scan_pool:
            iid = _to_int_id(obj.get('id', None))
            if iid is not None:
                existing_ids.append(iid)

        next_id = (max(existing_ids) + 1) if existing_ids else 2000001

        # 添加新单位
        if 'add_units' in modifications:
            for add_config in modifications['add_units']:
                unit_type = add_config['type']
                player = add_config['player']
                base_position = add_config['position']
                rotation = add_config.get('rotation', 0)
                count = add_config.get('count', 1)

                for _ in range(count):
                    # 为多个单位添加随机偏移
                    offset_x = offset_y = 0.0
                    if count > 1:
                        offset_x = random.uniform(-2, 2)
                        offset_y = random.uniform(-2, 2)

                    # 计算位置与高度
                    if isinstance(base_position, (list, tuple)) and len(base_position) >= 3:
                        x, y, z = float(base_position[0]) + offset_x, float(base_position[1]) + offset_y, float(base_position[2])
                    elif isinstance(base_position, (list, tuple)) and len(base_position) >= 2:
                        x, y = float(base_position[0]) + offset_x, float(base_position[1]) + offset_y
                        z = self.terrain_analyzer.get_height_at_position(x, y)
                    else:
                        # 不规范输入，兜底
                        x, y = 16.0 + offset_x, 16.0 + offset_y
                        z = self.terrain_analyzer.get_height_at_position(x, y)

                    position_str = f"{x},{y},{z}"
                    unit_rotation = rotation + (random.uniform(-0.5, 0.5) if count > 1 else rotation)

                    if is_mixed_schema:
                        new_unit = {
                            "tag": "ObjectUnit",
                            "id": str(next_id),
                            "type": unit_type,
                            "player": str(player),
                            "position": position_str,
                            "rotation": str(unit_rotation),
                            "scale": "1,1,1"
                        }
                    else:
                        new_unit = {
                            "id": str(next_id),
                            "type": unit_type,
                            "player": str(player),
                            "position": position_str,
                            "rotation": str(unit_rotation),
                            "scale": "1,1,1"
                        }

                    new_units.append(new_unit)
                    next_id += 1

                print(f"➕ 添加了 {count} 个 {unit_type} (玩家{player})")

        # 组装返回（与输入结构保持一致）
        if is_mixed_schema:
            result = preserved_other + new_units
        else:
            result = new_units

        print(f"📊 修改后单位数量: {len(new_units)}；返回总对象数: {len(result)}")
        return result

    def _generate_objects_xml(self, objects):
        """生成 Objects XML 文件"""
        root = ET.Element("PlacedObjects", Version="27")

        for obj in objects:
            if obj["tag"] == "ObjectUnit":
                unit_elem = ET.SubElement(root, "ObjectUnit")
                unit_elem.set("Id", obj['id'])
                unit_elem.set("Position", obj['position'])
                unit_elem.set("Rotation", obj['rotation'])
                unit_elem.set("Scale", obj['scale'])
                unit_elem.set("UnitType", obj['type'])
                unit_elem.set("Player", obj['player'])
            else:
                # 还原非单位对象（原封不动保留）
                other_elem = ET.SubElement(root, obj["tag"])
                for k, v in obj["attrib"].items():
                    other_elem.set(k, v)

        xml_str = ET.tostring(root, encoding='utf-8', xml_declaration=True)
        return xml_str.decode('utf-8')

    def _extract_file_from_map(self, map_path, filename):
        """从地图中提取单个文件"""
        try:
            # 打开MPQ档案
            mpq_handle = wintypes.HANDLE()
            success = self.lib.SFileOpenArchive(map_path, 0, 0, ctypes.byref(mpq_handle))

            if success == 0:
                return None

            # 提取文件
            file_bytes = filename.encode('utf-8')
            has_file = self.lib.SFileHasFile(mpq_handle, file_bytes)

            if has_file == 0:
                self.lib.SFileCloseArchive(mpq_handle)
                return None

            # 打开文件
            file_handle = wintypes.HANDLE()
            open_success = self.lib.SFileOpenFileEx(mpq_handle, file_bytes, 0, ctypes.byref(file_handle))

            if open_success == 0:
                self.lib.SFileCloseArchive(mpq_handle)
                return None

            # 获取文件大小
            file_size = self.lib.SFileGetFileSize(file_handle, None)
            if file_size == 0xFFFFFFFF:
                self.lib.SFileCloseFile(file_handle)
                self.lib.SFileCloseArchive(mpq_handle)
                return None

            # 读取文件内容
            buffer = ctypes.create_string_buffer(file_size)
            bytes_read = wintypes.DWORD()

            read_success = self.lib.SFileReadFile(file_handle, buffer, file_size, ctypes.byref(bytes_read), None)
            self.lib.SFileCloseFile(file_handle)
            self.lib.SFileCloseArchive(mpq_handle)

            if read_success == 0:
                return None

            return buffer.raw[:bytes_read.value]

        except Exception as e:
            return None

    def _replace_files_in_map(self, output_path, modified_files):
        """用 StormLib 替换修改的文件"""
        print(f"🔥 替换文件到地图: {os.path.basename(output_path)}")

        try:
            # 打开MPQ
            mpq_handle = wintypes.HANDLE()
            success = self.lib.SFileOpenArchive(output_path, 0, 0, ctypes.byref(mpq_handle))

            if success == 0:
                error = self.get_last_error()
                raise Exception(f"打开MPQ失败，错误代码: {error}")

            print("✅ MPQ打开成功")

            # 替换修改的文件
            replaced_count = 0
            for filename, file_path in modified_files:
                mpq_file_path = filename.replace(os.sep, '\\')

                if self._add_file(mpq_handle, file_path, mpq_file_path):
                    replaced_count += 1
                    print(f"  ✓ 替换 {mpq_file_path}")
                else:
                    print(f"  ✗ 替换失败 {mpq_file_path}")

            # 压缩和关闭
            self.lib.SFileCompactArchive(mpq_handle, None, False)
            self.lib.SFileCloseArchive(mpq_handle)

            print(f"✅ 替换文件完成，替换了 {replaced_count} 个文件")
            return True

        except Exception as e:
            print(f"❌ 替换文件失败: {e}")
            return False

    def _add_file(self, mpq_handle, local_file_path, mpq_file_path):
        """添加文件到MPQ"""
        try:
            local_abs_path = os.path.abspath(local_file_path)
            mpq_file_bytes = mpq_file_path.encode('utf-8')

            # 检查文件是否存在
            if not os.path.exists(local_abs_path):
                print(f"  ❌ 本地文件不存在: {local_abs_path}")
                return False

            # 获取文件大小
            file_size = os.path.getsize(local_abs_path)
            print(f"  📁 准备替换文件: {mpq_file_path} ({file_size} 字节)")

            # 使用MPQ_FILE_REPLACEEXISTING标志替换现有文件
            MPQ_FILE_REPLACEEXISTING = 0x80000000

            success = self.lib.SFileAddFileEx(
                mpq_handle, local_abs_path, mpq_file_bytes,
                MPQ_FILE_REPLACEEXISTING,  # 替换现有文件
                0,  # 不使用压缩
                0
            )

            if success == 0:
                error_code = self.get_last_error()
                print(f"  ❌ 文件替换失败: {mpq_file_path}, 错误码: {error_code}")
                return False

            print(f"  ✅ 文件替换成功: {mpq_file_path}")
            return True

        except Exception as e:
            print(f"  ❌ 添加文件异常: {mpq_file_path} - {e}")
            return False

    def create_battle_scenario(self, source_map_path, output_path, battle_config):
        """创建战斗场景

        battle_config = {

            'scenario_type': 'pvp' | 'pve' | 'pvt' | 'zvt' | 'zvz' | 'tvt',
            'player1_units': [{'type': 'Marine', 'count': 10, 'position': (10, 10)}],
            'player2_units': [{'type': 'Zealot', 'count': 8, 'position': (30, 30)}],
            'clear_existing': True/False
        }
        """
        print(f"\n=== 创建战斗场景: {battle_config.get('scenario_type', 'custom')} ===")

        modifications = {
            'clear_all': battle_config.get('clear_existing', True),
            'add_units': []
        }

        # 添加玩家1单位
        if 'player1_units' in battle_config:
            for unit_config in battle_config['player1_units']:
                modifications['add_units'].append({
                    'type': unit_config['type'],
                    'player': 1,
                    'position': unit_config['position'],
                    'count': unit_config.get('count', 1),
                    'rotation': unit_config.get('rotation', 0)
                })

        # 添加玩家2单位
        if 'player2_units' in battle_config:
            for unit_config in battle_config['player2_units']:
                modifications['add_units'].append({
                    'type': unit_config['type'],
                    'player': 2,
                    'position': unit_config['position'],
                    'count': unit_config.get('count', 1),
                    'rotation': unit_config.get('rotation', 0)
                })

        return self.modify_map_units(source_map_path, output_path, modifications)


def parse_task_json(file_path):
    """
    读取task.json文件并转换为intelligent_config格式

    Args:
        file_path (str): task.json文件路径

    Returns:
        dict: 转换后的intelligent_config格式字典
    """

    def parse_position(pos_str):
        """解析位置字符串，例如 " (9, 32)" -> [9, 32, 0]"""
        # 使用正则表达式提取数字
        numbers = re.findall(r'\d+', pos_str.strip())
        if len(numbers) >= 2:
            return [int(numbers[0]), int(numbers[1]), 0]
        else:
            return [0, 0, 0]  # 默认位置

    def parse_count(num_str):
        """解析数量字符串，例如 " 5" -> 5"""
        return int(num_str.strip())

    try:
        # 读取JSON文件
        with open(file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)

        # 初始化配置
        intelligent_config = {
            'scenario_type': scenario_type,
            'clear_existing': True,
            'player1_units': [],
            'player2_units': []
        }

        # 处理agent（player1）单位
        if 'agent' in data:
            for agent_key, agent_info in data['agent'].items():
                unit_config = {
                    'type': agent_info['type'],
                    'count': parse_count(agent_info['num']),
                    'position': parse_position(agent_info['pos'])
                }
                intelligent_config['player1_units'].append(unit_config)

        # 处理enemy（player2）单位
        if 'enemy' in data:
            for enemy_key, enemy_info in data['enemy'].items():
                unit_config = {
                    'type': enemy_info['type'],
                    'count': parse_count(enemy_info['num']),
                    'position': parse_position(enemy_info['pos'])
                }
                intelligent_config['player2_units'].append(unit_config)

        return intelligent_config

    except FileNotFoundError:
        print(f"错误：找不到文件 {file_path}")
        return None
    except json.JSONDecodeError:
        print(f"错误：JSON文件格式不正确")
        return None
    except Exception as e:
        print(f"错误：{str(e)}")
        return None




def get_available_template_maps(file_path):
    """获取可用的模板地图"""
    template_dirs = [
        r"E:\StarCraft II\Maps\terrain_maps",
        r"E:\game\StarCraft II\Maps\smac-hard-map",
        r"E:\game\StarCraft II\Maps\VLM_ATTENTION",
        r".\Maps\simple_battle_maps\final_maps"
    ]

    maps = []
    for dir_path in template_dirs:
        if os.path.exists(dir_path):
            for file in os.listdir(dir_path):
                if file.endswith(file_path):

                    maps.append(os.path.join(dir_path, file))
            if maps:
                break

    return maps


def extract_json_from_markdown(text):
    """从markdown格式的文本中提取JSON代码块"""
    pattern = r'```json\s*\n(.*?)\n```'
    match = re.search(pattern, text, re.DOTALL)
    if match:
        json_str = match.group(1)
        return json.loads(json_str)
    return None


# 方法2: 查找大括号包围的JSON内容
def extract_json_by_braces(text):
    """通过查找大括号来提取JSON内容"""
    start = text.find('{')
    if start == -1:
        return None

    brace_count = 0
    end = start

    for i, char in enumerate(text[start:], start):
        if char == '{':
            brace_count += 1
        elif char == '}':
            brace_count -= 1
            if brace_count == 0:
                end = i + 1
                break

    if brace_count == 0:
        json_str = text[start:end]
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            return None
    return None


def extract_json_robust(text):
    """更健壮的JSON提取方法"""
    # 首先尝试从markdown代码块提取
    result = extract_json_from_markdown(text)
    if result:
        return result

    # 如果失败，尝试查找大括号
    result = extract_json_by_braces(text)
    if result:
        return result

    # 其他尝试...
    lines = text.split('\n')
    json_lines = []
    in_json = False

    for line in lines:
        if line.strip().startswith('{'):
            in_json = True
            json_lines.append(line)
        elif in_json:
            json_lines.append(line)
            if line.strip().endswith('}') and line.count('}') >= line.count('{'):
                break

    if json_lines:
        json_str = '\n'.join(json_lines)
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            return None

    return None



def test_stormlib_unit_editor(task_file_path, input_file_path, output_file_path):


    """测试函数 - 修正版"""
    print("🧪 测试 StormLib 单位编辑器 (智能配置版)")

    try:
        editor = StormLibUnitEditor()
    except FileNotFoundError as e:
        print(f"❌ StormLib 初始化失败: {e}")
        print("请确保 StormLib.dll 在正确的路径")
        return False

    # 获取可用模板
    template_maps = get_available_template_maps(input_file_path)
    if not template_maps:
        print("❌ 没有找到可用的模板地图")
        return False

    template_map = template_maps[0]
    print(f"📁 使用模板地图: {os.path.basename(template_map)}")

    # # 创建输出目录

    # output_dir = "/StarCraft II/Maps/"

    # if not os.path.exists(output_dir):
    #     os.makedirs(output_dir)

    try:
        # 1. 分析地图地形
        print("\n=== 地形分析阶段 ===")
        terrain_analyzer = editor.analyze_map_terrain(template_map)

        # 2. 分析现有单位
        print("\n=== 单位分析阶段 ===")
        original_units = editor.analyze_map_units(template_map)

        # 3. 加载单位数据库 - 添加错误处理
        print("\n=== 加载单位数据库 ===")
        units_data_path = r".\units.json"
        if not os.path.exists(units_data_path):
            print(f"❌ 单位数据文件不存在: {units_data_path}")
            # 使用默认单位数据
            units_data = {
                "Marine": {"name": "陆战队员", "type": "ground"},
                "Zealot": {"name": "狂热者", "type": "ground"},
                "Stalker": {"name": "追猎者", "type": "ground"},
                "Marauder": {"name": "掠夺者", "type": "ground"}
            }
            print("✅ 使用默认单位数据")
        else:
            with open(units_data_path, "r", encoding="utf-8") as file:
                units_data = json.load(file)
            print(f"✅ 加载了 {len(units_data)} 种单位类型")

        # 4. 初始化 LLM 客户端 - 添加错误处理
        print("\n=== 初始化 LLM 客户端 ===")
        try:
            client = openai.OpenAI(
                api_key="sk-5e857bd086c1417ea1ef4820e92b2aaf",
                base_url="https://api.deepseek.com"
            )
            print("✅ LLM 客户端初始化成功")
        except Exception as e:
            print(f"❌ LLM 客户端初始化失败: {e}")
            client = None

        # 5. 生成智能配置
        print("\n=== 生成智能战斗配置 ===")

        intelligent_config = parse_task_json(task_file_path)
        print("the config is :" )
        print(intelligent_config)

        # 6. 显示生成的配置 - 安全访问
        print("\n📋 生成的战斗配置:")

        if intelligent_config is not None:
            print(f"  清除现有单位: {intelligent_config.get('clear_existing', False)}")
        

            # 安全计算单位总数
            total_p1_units = 0
            total_p2_units = 0

            if 'player1_units' in intelligent_config and intelligent_config['player1_units']:
                total_p1_units = sum(unit.get('count', 1) for unit in intelligent_config['player1_units'])

            if 'player2_units' in intelligent_config and intelligent_config['player2_units']:
                total_p2_units = sum(unit.get('count', 1) for unit in intelligent_config['player2_units'])

            print(f"  玩家1单位总数: {total_p1_units}")
            print(f"  玩家2单位总数: {total_p2_units}")

            # 详细显示单位配置 - 安全访问
            for player_num, player_key in enumerate(['player1_units', 'player2_units'], 1):
                if player_key in intelligent_config and intelligent_config[player_key]:
                    print(f"  玩家{player_num}部队:")
                    for unit_config in intelligent_config[player_key]:
                        if isinstance(unit_config, dict):
                            pos = unit_config.get('position', [0, 0, 0])
                            if isinstance(pos, (list, tuple)) and len(pos) >= 3:
                                print(
                                    f"    - {unit_config.get('count', 1)}x {unit_config.get('type', 'Unknown')} @ ({pos[0]:.1f}, {pos[1]:.1f}, {pos[2]:.1f})")
                            else:
                                print(f"    - {unit_config.get('count', 1)}x {unit_config.get('type', 'Unknown')} @ (位置无效)")
        else:
            print("  清除现有单位: False (配置为空)")

        # 7. 创建战斗场景
        print("\n=== 创建战斗场景 ===")

        battle_success = editor.create_battle_scenario(template_map, output_file_path, intelligent_config)


        return battle_success

    except Exception as e:
        print(f"❌ 测试过程发生异常: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":

    time_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    # 构建log目录路径 - 使用绝对路径
    log_dir = os.path.abspath(os.path.join("log", time_str))
    
    # 创建目录（包括父目录log）
    os.makedirs(log_dir, exist_ok=True)
    print(f"📁 创建日志目录: {log_dir}")
    
    # 修复输出路径构建
    output_map = os.path.join(log_dir, "test.SC2Map")
    print(f"📁 输出地图路径: {output_map}")
    
    # 确保输出目录存在
    os.makedirs(os.path.dirname(output_map), exist_ok=True)
    
    # 执行测试并检查结果
    test_stormlib_unit_editor(r".\task.json", map_name + ".SC2Map", "test.SC2Map")

    # dst = os.path.join("E:", "StarCraft II", "maps", "test1.SC2Map")

    # os.makedirs(os.path.dirname(dst), exist_ok=True)

    # os.remove(dst)

    # shutil.copy(output_map, dst)
 

