#!/usr/bin/env python3
"""CTGoodJobs 自动申请 — 继承 BaseApplier"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from shared.base_applier import BaseApplier
from shared import utils


class CTGoodJobsApplier(BaseApplier):
    PLATFORM = "CTGoodJobs"
    MAP_PREFIX = "ctgoodjobs_"

    def detect_mode(self) -> str:
        result = utils.bb_eval("""(function(){
            var btns = document.querySelectorAll('button');
            for(var i=0;i<btns.length;i++){
                if((btns[i].textContent||'').trim()==='1-Click Apply' && btns[i].offsetParent){
                    return 'MODE:1click';
                }
            }
            var links = document.querySelectorAll('a');
            for(var j=0;j<links.length;j++){
                var t = (links[j].textContent||'').trim();
                if(t==='Apply Now' && links[j].offsetParent){
                    var href = links[j].href||'';
                    if(href.indexOf('count_job_detail')>=0) return 'MODE:external';
                    return 'MODE:link';
                }
            }
            return 'MODE:unknown';
        })()""")
        if "1click" in result: return "auto"
        if "external" in result: return "external"
        return "unknown"

    def execute_apply(self) -> bool:
        # 点击 1-Click Apply
        utils.bb_eval("""(function(){
            var btns=document.querySelectorAll('button');
            for(var i=0;i<btns.length;i++){
                if((btns[i].textContent||'').trim()==='1-Click Apply'&&btns[i].offsetParent){
                    btns[i].click();return'OK';
                }
            }
            return'NO';
        })()""")
        utils.bb_wait(5000)

        # 检查是否直接 Applied（直达型）
        check = utils.bb_eval("""(function(){
            var btns=document.querySelectorAll('button');
            for(var i=0;i<btns.length;i++){
                if(btns[i].className.indexOf('btn--success')>=0 && (btns[i].textContent||'').trim()==='Applied'){
                    return 'ALREADY_APPLIED';
                }
            }
            return 'NOT_YET';
        })()""")
        if check == "ALREADY_APPLIED":
            print("    ✅ 1-Click 直达（按钮已变 Applied）")
            return True

        # 填表型：找 Send To Employer
        r = utils.bb_eval("""(function(){
            var a=document.querySelector('a.submit-hl-btn');
            if(a&&a.offsetParent){a.click();return'CLICKED';}
            var d=document.querySelector('.submit');
            if(d&&d.offsetParent&&(d.textContent||'').indexOf('Send To Employer')>=0){d.click();return'CLICKED div';}
            return'NO';
        })()""")
        print(f"    Send To Employer: {r}")
        utils.bb_wait(5000)

        # 检查成功
        url = utils.bb_eval("location.href")
        if "apply_complete_member" in url:
            return True
        # fallback: 再查 Applied 按钮
        check2 = utils.bb_eval("""(function(){
            var btns=document.querySelectorAll('button');
            for(var i=0;i<btns.length;i++){
                if(btns[i].className.indexOf('btn--success')>=0)return'APPLIED';
            }
            return'NO';
        })()""")
        return check2 == "APPLIED"


if __name__ == "__main__":
    CTGoodJobsApplier(Path(__file__).parent).cli()
