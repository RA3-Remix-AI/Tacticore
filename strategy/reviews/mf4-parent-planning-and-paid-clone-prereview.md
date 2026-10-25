# MF4 父层任务与paid clone预审

只读审阅及纯测试，不运行SDK/GUI/模型，不修改Root/Native/Production源码。MF4完整原生/校验器尚未最终冻结，本结论仅为前置审阅，不发整体现场Go、不授证。

独立运行 `test_mission4_planning_client` 三项全部通过：父层不计算仍在自然移动的pair路线，不调用 `_role_route_pair`；删除旧route，仅传可信history路径和typed pair意图；没有history或没有已证surface/admission的演员不排单。queued不等于started，更不等于借出控制。实际worker/q/gate使用新MF4明确目录，演员helper由可信schema选择，不能取model/receipt文件名。

MF4 `continuous_paid_driver.py` 实际SHA `d298b1672d1be8d7d56c98841b2280837289c3698355d2bc7aab89b899a927aa`。独立与实际冻结ca8e8b4a原件逐行diff：仅CLI `--mission` choices限formation，以及删除实际formation调用中的旧 `--wrapper-filename lease_admission_v2.py` 参数对。HERE自然改为新目录；其余逐行相同。4000预算、1000reserve、正常付款/出厂/live链、生产stop/31/active0、5唯一真实入口字节及one-child交接门槛保留。

编译/文件准备可继续。后续需独立审原生停稳后规划握手、route回写与锁、FOV/来源伤害、失败双角色清理、版本指纹及实际typed路由，真实raw完整链之前不能授MF4 source能力。
