
import os
import logging
from pykis.kis import PyKis
from dotenv import load_dotenv

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

def check_current_balance():
    load_dotenv()
    
    app_key = os.getenv("APP_KEY")
    app_secret = os.getenv("APP_SECRET")
    hts_id = os.getenv("HTS_ID")
    account_number = os.getenv("ACCOUNT_NUMBER")

    api = PyKis(
        id=hts_id,
        account=account_number,
        appkey=app_key,
        secretkey=app_secret,
        virtual_appkey=app_key,
        virtual_secretkey=app_secret,
        use_websocket=False
    )

    try:
        acc = api.account()
        print(f"=== 계좌 정보 [{acc.account_number.number}] ===")
        
        res = api.fetch(
            "/uapi/domestic-stock/v1/trading/inquire-psbl-order",
            api="VTTC8435R",
            params={
                "CANO": acc.account_number.number,
                "ACNT_PRDT_CD": acc.account_number.code,
                "PDNO": "005930",
                "ORD_UNPR": "0",
                "ORD_DVSN": "01",
                "CMA_EVLU_AMT_ICLD_YN": "Y",
                "OVRS_ICLD_YN": "N"
            },
            domain="virtual"
        )
        
        if res and hasattr(res, "output"):
            out = res.output
            print("\n[매수가능조회 (VTTC8435R) 결과]")
            # KisDynamicDict는 속성으로 직접 접근하거나 dict() 변환이 필요함
            print(f"- nrcv_buy_amt (미수없는 매수가능금액): {getattr(out, 'nrcv_buy_amt', 'N/A')}원")
            print(f"- ord_psbl_cash (주문가능현금): {getattr(out, 'ord_psbl_cash', 'N/A')}원")
            print(f"- max_buy_amt (최대매수금액): {getattr(out, 'max_buy_amt', 'N/A')}원")
        
        res2 = api.fetch(
            "/uapi/domestic-stock/v1/trading/inquire-balance",
            api="VTTC8434R",
            params={
                "CANO": acc.account_number.number,
                "ACNT_PRDT_CD": acc.account_number.code,
                "AFHR_FLPR_YN": "N",
                "OFL_YN": "",
                "INQR_DVSN": "02",
                "UNPR_DVSN": "01",
                "FUND_STTL_ICLD_YN": "N",
                "FUTS_LST_STTL_ICLD_YN": "N",
                "D2_NOMS_SCTR_REMN_YN": "N",
                "CPSN_ICLD_YN": "N",
                "PRCS_DVSN": "00",
                "CTX_AREA_FK100": "",
                "CTX_AREA_NK100": ""
            },
            domain="virtual"
        )
        
        if res2 and hasattr(res2, "output2") and res2.output2:
            out2 = res2.output2[0]
            print("\n[주식잔고조회 (VTTC8434R) 결과]")
            print(f"- dnca_tot_amt (예수금총금액): {getattr(out2, 'dnca_tot_amt', 'N/A')}원")
            print(f"- nxdy_excc_amt (익일결제예정금액): {getattr(out2, 'nxdy_excc_amt', 'N/A')}원")
            print(f"- tot_evlu_amt (총평가금액): {getattr(out2, 'tot_evlu_amt', 'N/A')}원")

    except Exception as e:
        print(f"오류 발생: {e}")

if __name__ == "__main__":
    check_current_balance()
