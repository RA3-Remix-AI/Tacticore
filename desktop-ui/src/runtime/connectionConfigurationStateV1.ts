/** Local configuration coherence only; ready never claims remote availability. */
export type ConnectionConfigurationState = 'unverified' | 'checking' | 'ready' | 'pending' | 'unknown';
export function configurationAdmissionNotice(state: ConnectionConfigurationState): string | null {
  switch (state) {
    case 'unverified': return '尚未核验本机连接配置，请前往“模型连接”初始化或重新查询连接；当前不能开始新的指挥。';
    case 'checking': return '正在核对本机连接配置；当前不能检查或启动新的指挥。';
    case 'pending': return '上次连接保存尚未完成核对，请前往“模型连接”核对未完成的保存；当前不能检查或启动新的指挥。';
    case 'unknown': return '本机连接配置尚未核验，请前往“模型连接”重新查询或核对保存结果；当前不能检查或启动新的指挥。';
    case 'ready': return null;
  }
}
