"""Prova real: empenhos lidos na TELA do portal (tela_portal/*.json, sem nomes) x banco ativo. Uso: python comparar_tela.py tela_portal/*.json"""
import json,sqlite3,pathlib,sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "app"))
from rp.painel import Painel
con=sqlite3.connect("file:"+pathlib.Path.home().joinpath("RestosAPagar_local/banco/restos_a_pagar.sqlite").as_posix()+"?mode=ro",uri=True)
tot={"iguais":0,"diferentes":0,"faltam_no_banco":0}
for arq in sys.argv[1:]:
    t=json.load(open(arq))
    uid=Painel(con).indicadores(t["exercicio"],t.get("data_final_banco",t["data_final"]),t["entidade"])["entidades"][0]["snapshot"]["snapshot_uid"]
    cid=con.execute("select id from coleta where snapshot_uid=?",(uid,)).fetchone()[0]
    db={(a,e):r for a,e,*r in con.execute("select anoempenho,empenho,proc_c,aproc_c,cancelado_proc_c,pago_proc_c,liquidado_c,cancelado_aproc_c,pago_aproc_c from rp_registro where normalizacao_id=13 and coleta_id=?",(cid,))}
    r1={"iguais":0,"diferentes":[],"faltam_no_banco":[]}
    for tb in t["tabelas"]:
        for emp,ins,liq,canc,pago in tb["rows"]:
            e,a=map(int,emp.split("/")); r=db.get((a,e))
            if r is None: r1["faltam_no_banco"].append(emp); continue
            p,ap,cp,pp,l,ca,pa=r
            esp=(p,None,cp,pp) if tb["tipo"]=="Processados" else (ap,l,ca,pa)
            if esp!=(ins,liq,canc,pago): r1["diferentes"].append({"empenho":emp,"tipo":tb["tipo"],"tela":[ins,liq,canc,pago],"banco":list(esp)})
            else: r1["iguais"]+=1
    print(pathlib.Path(arq).name, "snapshot", uid[:8], json.dumps(r1, ensure_ascii=False))
    tot["iguais"]+=r1["iguais"]; tot["diferentes"]+=len(r1["diferentes"]); tot["faltam_no_banco"]+=len(r1["faltam_no_banco"])
print(tot)
