# main-mct3-02 独立只读复核

原始报告 SHA：`79463af97f60cdee0287a46501a06364fc1d33b01e49f62d175ba1f7c5d0259a`。原件未修改。

实际 actor1143 租约为 detach seq4/frame6614 至 return完成 seq49/frame6630。最终 native_move=2 来自安装期前 frame6613/seq2 和归还后 frame6643/seq52；真实租约内未观察到 tag0 Move。首次计数已在6615触发 reason10，后一次发生于退出后，不能作为当时退出原因。

晚绑定退点通过：6610 的同演员只读样本 HP100/status0，位置写入同一 mission retreat_point；issued6614 与采样相隔4帧，核心校验 resolved_actual_implicit_origin=True。正常池归还1次，restore16383、active0。

本例保持失败，无接近效果、来源伤害或完整任务效果资格。新版本可修计数租约边界，但不得追认本例。新 MCT/MFM 必须仍在每个演员实际借出期间识别未标记外来命令，同帧以原生调用次序区分，归还后原生重新招募属于合法动作。
