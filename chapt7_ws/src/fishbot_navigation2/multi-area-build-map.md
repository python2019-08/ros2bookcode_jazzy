# ch01.分区域建图与地图合并（FishBot / Gazebo Harmonic）

> 问题：房子左下是大厅，左上、右上、右下各是房间，中间是十字形通道。左侧建图正常，
> 移动到右侧时整个地图突然垮掉。能否把房子分成多个区域分别建图，最后合并成一张完整地图，
> 让每个区域的误差累积不会把整张图拉垮？
>
> 环境：ROS 2 Jazzy + Gazebo Harmonic + slam_toolbox（online async）+ ros2_control diff drive。

**结论：可以，你的 slam_toolbox 自带合并功能（`merge_maps_kinematic`）。但先别急着分区：
你这个“突然垮掉”大概率不是误差累积，而是一次扫描匹配失败或假回环。分区能绕过它，但绕不过根因。**

---

## 1. 为什么不太像累积误差

- 仿真里用的是轮子位置反馈：`open_loop: false`、`position_feedback: true`
  （`config/fishbot_ros2_controller.yaml:48-49`），odom 漂移很小。
- 累积误差表现为渐变，重影会一点点变大；而“整个地图突然垮掉”是阶跃，
  典型是位姿图被一条错误约束整体拉歪。
- 保存的 `maps/room02.pgm` 里有大片放射状 / 扇形拖影，还有一面明显歪掉的墙——
  这是“某几帧扫描被放到了错误位姿”的形态，不是慢慢漂出来的重影。

## 2. 两个最可疑的点

### 2.1 雷达量程正好卡在 8 m

```yaml
# config/slam_toolbox_mapping.yaml:37
max_laser_range: 8.0        # gpu_lidar 的 <max> 也是 8.0
```

Gazebo 打不到东西时返回的就是 max = 8.0，和真实 8.0 m 读数完全同值。
房子是 19 × 11 m（对角线约 22 m），大厅中央和长走廊里会有大量光束打空——
这些“无回波”点在地图里就是一圈跟着机器人走的假边界，也是匹配变差的来源。
slam_toolbox 默认 `max_laser_range` 本来就是 20.0，压到 8.0 等于把边界情况直接交给匹配器。

### 2.2 回环参数对这种对称布局偏松

```yaml
loop_search_maximum_distance: 5.0          # 默认 3.0，调大了
loop_search_space_dimension: 8.0           # 默认值，但房子宽度才 11 m
loop_match_minimum_response_coarse: 0.35   # 默认
loop_match_minimum_response_fine: 0.45     # 默认
```

四角都是房间、中间十字走廊，房间之间长得很像。8 m 的搜索窗足够把一个房间
匹配到另一个房间。一旦接受假回环，slam_toolbox 会做全局优化——
表现就是“整张图瞬间垮掉”。

顺带排掉一个干扰项：`enable_interactive_mode: true`（:42）意味着 RViz 里
位姿图是可拖动的，鼠标误拖一个节点也会触发一次大修正。建图时建议关掉。

## 3. 先做的验证（5 分钟）

1. 把 `config/slam_toolbox_mapping.yaml:55` 改成 `do_loop_closing: false`，
   同时 `enable_interactive_mode: false`，跑同一条路线。
   - 图不再垮（可能有接缝或轻微漂移）→ 假回环实锤。
   - 注意：这个版本的 slam_toolbox **没有**运行时开关回环的服务；
     `slam_toolbox/manual_loop_closure` 只是交互模式下手动改位姿，不是开关。
     只能改参数重启。
2. 如果关了回环还是垮，那就不是回环问题，而是 TF 或扫描匹配：
   录一段 bag（不要同时开 slam_toolbox，避免旧 map→odom 混进来）：

   ```bash
   ros2 bag record -o src/fishbot_navigation2/bags/raw1 \
     /scan /tf /tf_static /odom /clock /cmd_vel
   ```

   之后用 `ros2 bag play --clock --rate 0.5` + 你的 `slam_mapping.launch.py`
   反复调参，不用重新开车。

## 4. 参数怎么改

```yaml
# gazebo_sensor_plugin.xacro:30  <max>8.0</max> -> <max>25.0</max>
# 房子对角线 22 m，20~25 m 都够；留 1~2 m 余量
max_laser_range: 23.0

# 回环收紧
loop_search_maximum_distance: 2.5
loop_search_space_dimension: 4.0
loop_match_minimum_chain_size: 15
loop_match_minimum_response_coarse: 0.45
loop_match_minimum_response_fine: 0.60

# 仿真里程计可信，让优化更贴 odom
distance_variance_penalty: 2.0
angle_variance_penalty: 2.0
```

暂时不想动雷达的话，至少把 `max_laser_range` 改成 `7.5`，
把 8.0 的无回波挡在阈值外。

操作上也有帮助：进大厅前先贴墙走一圈、不要在空旷处原地旋转、
每段轨迹尽量闭环回起点。

## 5. 真要分区：两条路

### 路线 A：同一起点 + 像素级叠加（仿真里最省事，推荐先试）

spawn 没有 `-x/-y`（`gazebo_sim.launch.py:71-79`），每次都在世界原点出生，
odom 也从同一处开始，所以每一段保存的 PGM **本来就处在同一个 map 坐标系**里，
不用做匹配。

- 每段单独重启一次仿真建图（大厅 + 左房一段，右侧上下两房各一段），
  区域间保留十字走廊一段重叠；
- 每段 `map_saver_cli` 存成 `region_a` / `region_b` / …；
- 合并规则：任一图是障碍 → 障碍；否则任一图是空白 → 空白；都未知 → 未知。
  按各 yaml 的 `origin` + `resolution` 直接叠。

好处：误差只留在自己区域内，不会有全局优化把整张图拉垮，也不用 RViz 手动对齐。

### 路线 B：官方 `merge_maps_kinematic`（已安装）

```bash
# 每段建完后保存位姿图（生成 region_a.posegraph / region_a.data）
ros2 service call /slam_toolbox/serialize_map slam_toolbox/srv/SerializePoseGraph \
  "{filename: '/home/abner/maps/region_a'}"

ros2 launch slam_toolbox merge_maps_kinematic_launch.py

ros2 service call /slam_toolbox/add_submap slam_toolbox/srv/AddSubmap \
  "{filename: '/home/abner/maps/region_a'}"
ros2 service call /slam_toolbox/add_submap slam_toolbox/srv/AddSubmap \
  "{filename: '/home/abner/maps/region_b'}"
```

然后在 RViz 里把 Fixed Frame 设为 `map`，加 Map 显示 `/map_1`、`/map_2`，
再加一个 `InteractiveMarkers` 显示、话题设成 `/merge_maps_tool/update`；
拖动 / 旋转子图，让走廊重叠区对齐。对齐后节点会自动发布
`/map` 和 `/map_metadata`。节点本身不写盘，最后：

```bash
mkdir -p /home/abner/maps
ros2 run nav2_map_server map_saver_cli -f /home/abner/maps/house_merged
```

关键注意：子图的初始位姿都是 identity（全部叠在原点），
**没有重叠区域就没法对齐**，所以分区时相邻区域一定要共享一段走廊。

## 6. 建议顺序

1. 关回环跑一趟，确认根因；
2. 改量程 + 收紧回环，再单趟建图；
3. 单趟能成就别分区。分区是保底方案，合并处仍然有接缝，
   导航到接缝附近可能有轻微错位。

---

*文档记录时间：2026-10-20*
