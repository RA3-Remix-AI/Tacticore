"""Package allowlisted public artifacts; never reads protected connection data."""
import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'acceptance')]
from assess_macro_desktop import load,sha


def package(out):
    if out.exists() or not out.is_relative_to(ROOT/'delivery'):raise ValueError('fresh_macro_delivery_required')
    original=ROOT/'delivery/commander-macro-20261028-progress-v1'
    old=load(original/'manifest.json')
    if any(sha(original/n)!=v['sha256'] for n,v in old['files'].items()):raise ValueError('staged_delivery_changed')
    out.mkdir()
    for name in old['files']:
        if name!='README.txt':shutil.copy2(original/name,out/name)
    files={
        'defense-timeline.html':'reports/macro-timeline-base-defense-11428-20261028-v1/macro-timeline.html',
        'defense-timeline.json':'reports/macro-timeline-base-defense-11428-20261028-v1/macro-timeline.json',
        'defense-timeline-review.json':'reports/macro-timeline-base-defense-11428-20261028-v1/browser-review.json',
        'defense-timeline-screen.png':'reports/macro-timeline-base-defense-11428-20261028-v1/browser-defense-detail.png',
        'defense-client-stopped.png':'acceptance/runs/20261028-133800-macro-probe/client-defense-feedback-stopped.png',
        'defense-settlement.png':'acceptance/runs/20261028-133800-macro-probe/research-settlement.png',
        'defense-natural.RA3Replay':'acceptance/runs/20261028-133800-macro-probe/research-natural.RA3Replay',
        'defense-public-config.json':'acceptance/runs/20261028-133800-macro-probe/battle-host/profile.json',
        'defense-diagnostics.json':str(Path.home()/'Downloads/tacticore-diagnostics-51c6a625-08a2-5769-86f4-03b3f937b096.json'),
        'restored-public-config.json':'reports/macro-base-defense-restored-profile-20261028.json',
        'style-restoration.json':'reports/macro-base-defense-style-restoration-20261028.json',
        'G6-capability-coverage.json':'reports/macro-capability-coverage-20261028-v1/assessment.json',
        'G7-complete-match.json':'reports/macro-complete-match-77280-20261028-v1/assessment.json',
        'G8-contribution-comparison.json':'reports/macro-contribution-comparison-20261028-v1/assessment.json',
        'model-base-defense.json':'reports/macro-desktop-base-defense-11428-20261028-v1/assessment.json',
        'defense-native-outcome.json':'reports/macro-outcome-11428-20261028-v1/assessment.json',
        'baseline-native-outcome.json':'reports/macro-baseline-outcome-77056-20261028-v1/assessment.json',
        'fixed-native-outcome.json':'reports/macro-fixed-outcome-72168-20261028-v1/assessment.json',
        'fixed-base-defense.json':'reports/macro-base-defense-assessment-72168-20261028-v1/assessment.json',
        'baseline-natural.RA3Replay':'acceptance/runs/20261028-093745-macro-probe/research-natural.RA3Replay',
        'fixed-natural.RA3Replay':'acceptance/runs/20261028-130743-macro-probe/research-natural.RA3Replay',
        'baseline-settlement.png':'acceptance/runs/20261028-093745-macro-probe/research-settlement.png',
        'fixed-settlement.png':'acceptance/runs/20261028-130743-macro-probe/research-settlement.png',
        'directed-construction.json':'reports/macro-desktop-construction-80688-20261028-v1/assessment.json',
        'production-user-stop.json':'reports/macro-desktop-production-68212-20261028-v2/assessment.json',
        'technology-budget.json':'reports/macro-budget-lifecycles-9284-20261028-v1/assessment.json',
        'regions-and-reassignment.json':'reports/macro-desktop-regions-9284-20261028-v1/assessment.json',
        'style-shadow-technology.json':'reports/macro-style-shadow-assessment-9284-20261028-v1/assessment.json',
        'style-shadow-scouting.json':'reports/macro-style-shadow-assessment-77356-20261028-v1/assessment.json',
        'executed-client.json':'acceptance/runs/20261028-133800-macro-probe/executed-client.json',
        'native-release.json':'acceptance/runs/20261028-133800-macro-probe/battle-host/macro-release.json',
        'owned-fixture-ended.json':'acceptance/runs/20261028-133800-macro-probe/fixture-ended.json',
        'macro-tests.log':'reports/macro-base-defense-macro-tests-20261028-v1.log',
        'host-tests.log':'reports/macro-base-defense-host-tests-20261028-v1.log',
        'strategy-tests.log':'reports/macro-base-defense-strategy-tests-20261028-v1.log',
        'ui-tests.log':'reports/macro-base-defense-ui-tests-20261028-v1.log',
        'client-build.log':'reports/macro-base-defense-client-build-20261028-v1.log'}
    for name,source in files.items():shutil.copy2(ROOT/source,out/name)
    readme='''弈核宏观指挥 · 本机验收交付 · 2026-10-28

打开 macro-timeline.html 可离线播放完整模型局的决策、战况及自然结算；无需服务器或模型连接。
打开 defense-timeline.html 可播放新版原生防守资格局的190个过程事件，支持播放、暂停与拖动。
两个HTML均内嵌数据；相邻JSON便于独立审阅。它们不播放单位动画。

模型决定宏观投入、建造偏好、兵种与队列数量、侦察时机及高层部署。原生AI继续负责选兵、寻路、阵型、目标选择、开火和技能。没有接管单兵操作。

验证范围：本机固定RA3 1.12、TemplePrime、P3苏军。经济/军队/科技预算；超级反应堆建造偏好；征召兵1、高射炮兵2/3、铁锤坦克1的逐项资格；原生选目标的侦察；两个公开固定区域及原生选己方建筑的防守。模型实战生产正效果为征召兵和高射炮兵，铁锤独立原语有效、模型目标存在未达标。建筑证据为队列与基础，不保证完成。数量表示新增原生队列接受，不保证出厂。
没有授予任意地图、任意扩张落点、任意选兵、独立追击/撤退控制器或逐单位命令。高层区域调度与改派由原生组任务消费，防守由原生StaticDefense/DefenseMicroManager执行，不把任务激活自动当成任务成功。

完整模型局PID77280：58次真实模型回复、52次原生计划，从开局到自然结算，模型方告负；G7-complete-match.json已通过。此局没有建造和区域命令，其他领域通过独立有界场景补齐。
新版防守局PID11428：20次真实回复、17次原生计划、10次防守意图；6次有对应原生效果和后续真实模型反馈，4次没有效果。实际客户端停止于9124帧，游戏继续至12794帧自然结算，模型方告负。它是定向资格与用户停止验证，不替代整局持续指挥样本。
G6-capability-coverage.json汇总所有宏观领域，明确建造和新版防守属于定向资格；G8-contribution-comparison.json区分配置、决策、原生采用、行为和结果。

对比：原生基线败、固定策略胜、原风格模型败。固定策略共2个意图、0次模型调用，结算前已释放。两组风格影子试验共12次真实响应，0次游戏访问与派发，不能计入实战。随机种子与策略窗口未统一、样本不足，不证明模型/风格提高胜率或实战因果效果。

原生录像说明：natural.RA3Replay是完整模型局；defense-natural、baseline-natural、fixed-natural分别来自各自同局。原生录像不保证重现外部宏观指令，保真验证仍未通过。宏观决策与回执应以本包离线时间线、截图、脱敏诊断和独立报告核对，不能把录像当作模型获胜或伤害归因证明。

原风格已通过实际UI恢复到修订15，除修订号外与原13公开字段一致。临时修订14只用于新版防守资格。全部研究游戏已按精确进程身份归档清理，停止后无新增指挥。
diagnostics.json、defense-diagnostics.json均由实际客户端下载，与原导出逐字节一致，不包含凭据、自由文本模型输入或原始响应正文。公开配置另行单列，连接凭据始终保留在本机原配置中。

本机客户端：C:\\Users\\Administrator\\Documents\\Red Alert 3\\bridge-probe\\desktop-ui\\src-tauri\\target\\debug\\tacticore-desktop.exe
这是现有工作区的开发构建；可播放时间线独立便携，客户端的独立安装/跨机器便携性未验收。当前登记绑定已结束的研究会话，不能对新进程沿用旧许可；新对局须通过本机可信fixture/session登记与检查后再在客户端启动。
实现、逐项证据原件、可信bootstrap与会话登记脚本保留在同一工作区。文档索引：bridge-probe/docs/commander-macro-evidence-index-20261028.md。
manifest.json列出本包每个文件的SHA256与大小。旧失败与未达标记录保留，未修改成成功。
'''
    (out/'README.txt').write_text(readme,encoding='utf8')
    manifest=dict(kind='macro_local_validated_delivery',session_id=old['session_id'],
        additional_session_id='f54f19e3-cc08-4a0f-beea-9c5ac215d23e',
        native_replay_fidelity_verified=False,client_cross_machine_portability_verified=False,
        credential_material_included=False,unit_micro_control=False,
        files={p.name:dict(sha256=sha(p),bytes=p.stat().st_size) for p in sorted(out.iterdir())})
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    if not all(sha(out/n)==v['sha256'] for n,v in manifest['files'].items()):raise ValueError('delivery_copy_mismatch')
    print(json.dumps(dict(output=str(out),files=len(manifest['files']),bytes=sum(v['bytes'] for v in manifest['files'].values()))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    package(p.parse_args().output.resolve())
