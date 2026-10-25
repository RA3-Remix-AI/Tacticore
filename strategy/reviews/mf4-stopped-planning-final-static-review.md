# MF4 停稳后规划最终独审

只读源码、文件指纹与本地纯测试，没有SDK、游戏读写、GUI或模型调用。按Root预授权已直接通知唯一runner立即开始首次串行现场诊断；本报告不授能力。

最终DLL：`1421d30446aa27712654b269edea52fcbe4abf5913e027bd1b45ffd230d948a4`；host：`2487f693f7ac71a746335258a019674243df36abe02ab7297474ef282758b531`；wrapper：`39b18c8d6cafead36276ab72a49f09a149f13bc319bb8cd3fd8872b8e41bcb6f`；q：`3d487ae9e3ec5b727ae9d50f814dbd05d5cf528e6c4ec73ca2a47260d9b042b3`。此前BE/d33候选未安装，不沿用。全部25本地文件和12外部依赖实际SHA匹配，详见同名JSON。

独立24项Python测试通过；另直接运行包含实际planning.cpp.inc的编译stub，27个正常、超时、未ready、坏generation、漂移、FOV、期限、HP、VT、同帧和bit0分支通过。stub没有游戏访问，且request_cleanup为模拟边界，不能冒充实机归还证明。

ABI880/7210012/events1052、WM383/magic4d464d34/v4与真实ctypes一致。13个hook表逐字等于旧MF3，没有添加新原生调用面。父层/field只给pair和正证覆盖，启动时route_count0；两actor实际Stop后三不同帧稳定才发布72。host从真实停点做受限2秒规划、逐来源/SHA/owner/surface、occupancy、admission、当前FOV与350原点排除，再把gen1数据写入、flush、gen2、flush、ready1原子发布。Native重新验证当前停点/几何/视野/期限，复制私有路线，发布双73与逐点74后才首Move；不由可变共享数组驱动后续路线。

6秒原生等待、心跳、撤销和原4500硬期限保留；坏计划/未知/超时走双actor正常cleanup，不能算效果。q从原始Stop/72/73/74/Move、计划文件和正证来源独立重建，不信ready/成功摘要。

零安装窗口修正两处：同逻辑帧重复Stop采样只表示没有新样本，既有双方稳定≥3时等待下一tick，真实fresh失稳仍失败；native surface mask由0x180收窄到0x181，与GroundV2一致排bit0。无门槛放宽，所有原始失败保持。

真实首次raw仍必须逐项证明有序阶段、front来源伤害、support位置配合、真实回撤、双actor正常归还与原始入口恢复。此静态Go不意味着SDK现场通过、战术有效或经济压制。
