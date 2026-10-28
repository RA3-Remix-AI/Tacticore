/** Fixed native export IDs only. No arbitrary local paths reach this flow. */
export interface DiagnosticRun {run_id:string;session_id:string;profile_id?:string;profile_revision?:number;effective_hash?:string}
export interface ExportReceipt {export_id:string;run_id:string;sha256:string;bytes:number;event_count:number;exported_event_count:number;truncated:boolean;redacted:true}
export interface DownloadedExport extends ExportReceipt {effective_profile_available:boolean}
type ExportRpc = (operation:'diagnostics.export',args:{run_id:string})=>Promise<unknown>;
type ReadExport = (command:'diagnostics_read',args:{exportId:string;expectedSha256:string})=>Promise<unknown>;
export type SaveExport = (filename:string,content:string)=>void;
export class DiagnosticError extends Error {constructor(public readonly code:string){super(code);}}
const object=(value:unknown):value is Record<string,unknown>=>typeof value==='object'&&value!==null&&!Array.isArray(value);
const uuid=(value:unknown):value is string=>typeof value==='string'&&/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(value);
const sha=(value:unknown):value is string=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value);
const count=(value:unknown):value is number=>typeof value==='number'&&Number.isSafeInteger(value)&&value>=0;

export function createDiagnosticsDownload(rpc:ExportRpc,read:ReadExport,save:SaveExport){
  return async(run:DiagnosticRun):Promise<DownloadedExport>=>{
    if(!uuid(run.run_id)||!uuid(run.session_id))throw new DiagnosticError('diagnostics_binding_invalid');
    const receipt=await rpc('diagnostics.export',{run_id:run.run_id});
    if(!object(receipt)||!uuid(receipt.export_id)||receipt.run_id!==run.run_id||!sha(receipt.sha256)
      ||!count(receipt.bytes)||receipt.bytes===0||receipt.bytes>8*1024*1024||!count(receipt.event_count)
      ||!count(receipt.exported_event_count)||receipt.exported_event_count>receipt.event_count
      ||typeof receipt.truncated!=='boolean'||receipt.truncated!==(receipt.exported_event_count<receipt.event_count)||receipt.redacted!==true)
      throw new DiagnosticError('diagnostics_receipt_invalid');
    let result:unknown;
    try{result=await read('diagnostics_read',{exportId:receipt.export_id,expectedSha256:receipt.sha256});}
    catch{throw new DiagnosticError('diagnostics_read_failed');}
    if(!object(result)||result.export_id!==receipt.export_id||result.sha256!==receipt.sha256
      ||result.bytes!==receipt.bytes||typeof result.content!=='string')throw new DiagnosticError('diagnostics_integrity_invalid');
    const bytes=new TextEncoder().encode(result.content);
    if(bytes.length!==receipt.bytes)throw new DiagnosticError('diagnostics_integrity_invalid');
    const digest=await crypto.subtle.digest('SHA-256',bytes);
    const actual=Array.from(new Uint8Array(digest),value=>value.toString(16).padStart(2,'0')).join('');
    if(actual!==receipt.sha256)throw new DiagnosticError('diagnostics_integrity_invalid');
    let document:unknown;
    try{document=JSON.parse(result.content);}catch{throw new DiagnosticError('diagnostics_document_invalid');}
    if(!object(document)||document.schema_version!==1||document.kind!=='tacticore_redacted_diagnostics'||document.redacted!==true
      ||document.export_id!==receipt.export_id||document.run_id!==run.run_id||!object(document.binding)
      ||document.binding.session_id!==run.session_id||(run.profile_id&&document.binding.commander_id!==run.profile_id))
      throw new DiagnosticError('diagnostics_binding_invalid');
    if(document.effective_profile_available===true){
      const profile=document.effective_profile;
      if(!object(profile)||(run.profile_id&&profile.profile_id!==run.profile_id)
        ||(run.profile_revision!==undefined&&profile.revision!==run.profile_revision)
        ||(run.effective_hash&&profile.effective_hash!==run.effective_hash))throw new DiagnosticError('diagnostics_binding_invalid');
    }else if(document.effective_profile_available!==false||document.effective_profile!==null){
      throw new DiagnosticError('diagnostics_document_invalid');
    }
    save(`tacticore-diagnostics-${receipt.export_id}.json`,result.content);
    return {...receipt,effective_profile_available:document.effective_profile_available} as unknown as DownloadedExport;
  };
}

export function saveDiagnosticFile(filename:string,content:string){
  const url=URL.createObjectURL(new Blob([content],{type:'application/json;charset=utf-8'}));
  const anchor=document.createElement('a');anchor.href=url;anchor.download=filename;
  document.body.append(anchor);anchor.click();anchor.remove();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
}
