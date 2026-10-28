export interface AppliedReceipt {state?:string;profile_id?:string;profile_revision?:number;effective_hash?:string}
export interface ConsumptionReceipt extends AppliedReceipt {model_response_received?:boolean;calls_started?:number;responses_returned?:number}
export function applicationView(profile:{profile_id:string;revision:number;effective:null|{effective_hash:string}}|undefined,
  applied:AppliedReceipt|undefined, consumption:ConsumptionReceipt|undefined) {
  const matches=(receipt:AppliedReceipt|undefined)=>!!profile?.effective && receipt?.profile_id===profile.profile_id
    && receipt.profile_revision===profile.revision && receipt.effective_hash===profile.effective.effective_hash;
  return {applied:matches(applied)&&applied?.state==='host_profile_applied',
    called:matches(consumption)&&(consumption?.calls_started??0)>0,
    responded:matches(consumption)&&consumption?.model_response_received===true&&(consumption.responses_returned??0)>0};
}
