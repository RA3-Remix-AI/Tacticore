# MFM3 admission-v4 驱动克隆预审

只读exact diff与文件SHA，没有修改驱动、原件或现场状态。初稿为Root两clone预审；后续wrapper/q最终冻结已完成统审，结果见末段及同目录 `mfm3-admission-v4-prefix-review.json`。

最终统审：wrapper0b455ffc、q00abec5e、pre248d9fd0、gate3fd817f8、prefix5e759c候选17项实际指纹匹配，10项新测试独立全过。额外纯边界核对距离恰60不删除，近20原点只删一个，原始后缀保持。q独立重算原plan/SHA、全部原source（含删点）、owner/ground、当前occupancy、prefix和Native真实route数组count；wrapper所有慢验证在最后采样前，两次fresh actor夹same-ID FOV，最后几何/350/期限不放宽。按Root预授权已直接通知唯一runner可首次串行现场诊断，不授能力、不追认旧失败。Native6324/e334与旧v3原样。

`field_coordinate_admission_v4.py` SHA `5403cf3cac27e7f0f6b0d639aa5f78e9fd7b0b3880e8fe6ca7838d90c55d6e4c`：相对v3 `6df9a1a5...`，仅argparse里wrapper_filename choices/default从lease_admission_v3改为lease_admission_v4；其余逐行一致。

`continuous_paid_formation_admission_v4.py` SHA `dd814a4a80ece3b7a799a4be42de0ea07c07d218146b6e602328cfce37ec22b3`：相对v3 `81913eda...`，仅formation实际子进程里的coordinate与wrapper两个路径3→4；付款、串行停止、5入口和完成链门槛不变。

读取原始run142348的suffix-review：late pose旧首点21.244m、14点几何失败；删除一个已走近点后首137.847m、13点全正逆几何通过；删除两个时首289.214m已经失败，继续多删也失败。此仅是旧实际位置上的纯几何诊断，不把旧exit64/0SDK改为成功。新q必须逐原点重算删除距离<60、只删前缀、保留2..16点原始后缀与全部来源，不插值、不删除未走近点，并重新做occupancy/geometry/FOV/350和启动期限检查。
