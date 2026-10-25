# MCT6 有界原生多发独立静态审阅

只读源码、文件指纹和纯测试，未安装原生组件、未调用SDK/游戏GUI/模型。按Root持续预授权，已直接通知唯一runner可进行首次现场诊断；本报告不授证。

最终候选DLL：`ed17953bcc916a007ea30694af703984598e8d148269f8ec23db3e5243bbd130`；host：`e58c5edbdce69e29e1c5c5b07b98ce5564002a797176acb48bf28d84910829c7`；wrapper：`a8f48bc291a19be1dc8de50c08180d1cf65b77593fe175aef8b1f9cb826f29e4`；核心q：`11db71035259efa285e3516224e95fc220b85eb360d1046c4b88de3c9388f692`。五个primary revision哈希逐实际文件一致。Event852/Tactical3490916/events1124与真实ctypes布局一致。

独立执行 `test_mission_combat_v6` 17项与 `test_mission6_client` 3项，20项全部通过。

早期安全Stop后3/4/5的loadout准备对外仍是approach，随后2接近、11最后prepare、6engage、7..10撤退恢复，公开阶段不倒退。使用一条normal ScriptAttack，保持原生正常多发/装填；交战最多300逻辑帧，基于当时可见目标HP建立min(150,20%)来源伤害目标，安全退出优先，partial即使恢复也不能冒completed。

同一已证AK entry的耗弹/装填由原始before/after、前次采样frame/tick和实际entry/asset重建，不信header计数。来源DamageInfo、Body HP提交、同目标与耗弹区间逐条关联；多个同帧命中不构成持续交战，至少有15帧命中跨度和交战跨度。现场仍须报告实际时长、伤害、耗弹和reload，不夸大为长期压制。

可见致死记录只读取同一次预可见同步调用的相同Body，约束同frame/thread/target ID/owner/template/BodyVT。已确认新增post ID/owner/template/VT字段由C++实际word读取，并非Python补造。死亡后不重新读隐藏坐标；HP夹0导致报文amount与实际差额不匹配时保持未知，不放宽来源归因。fixture的负HP致死正例仅测试协议，不是现场致死证据。

客户端实际worker的fakechild测试确认新V6 wrapper/权威q/正常Stop共享映射路由；独立14入口校验对实际EXPECTED EXE逐字节比对。旧V5与历史失败保持原样，未升级旧证据。真实新raw必须完整证明有记忆接近、当前FOV重获、同订单多发来源伤害、真实回点和控制释放后，才能由可信宿主授予新目的能力；经济压制仍未证明。
