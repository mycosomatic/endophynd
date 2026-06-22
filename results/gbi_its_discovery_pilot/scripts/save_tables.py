#!/usr/bin/env python3
"""Dump the pilot result tables into results/gbi_its_discovery_pilot/."""
import re, collections, csv, os

TMP="/home/harte/endophynd_cache/cold/tmp/gbi_discovery"
DST="/home/harte/endophynd/endophynd/results/gbi_its_discovery_pilot"
os.makedirs(DST, exist_ok=True)

# recovery stats from the run log (process-then-delete; intermediates not retained)
REC={
 "SRR30183952":dict(species="Silene_verecunda", family="Caryophyllaceae",
    d28="positive", total_reads=230708785, baited=1202249, unique=210128, its1=20623, its2=1397),
 "SRR30183458":dict(species="Streptanthus_glandulosus", family="Brassicaceae",
    d28="negative", total_reads=219969757, baited=11075239, unique=1118516, its1=85138, its2=6117),
}
ORDER=["SRR30183952","SRR30183458"]

def lineage(sseqid):
    parts=sseqid.split("|"); tax=parts[4] if len(parts)>=5 else ""
    d={}
    for f in tax.split(";"):
        if "__" in f: r,v=f.split("__",1); d[r]=v
    return d

def parse(acc):
    best={}
    for line in open(f"{TMP}/{acc}.blast.tsv"):
        f=line.rstrip("\n").split("\t")
        if len(f)<4: continue
        q,s,pid,ln=f[0],f[1],float(f[2]),int(f[3])
        if q not in best or pid>best[q][0]: best[q]=(pid,ln,s)
    genus=collections.Counter(); genus_uniq=collections.Counter(); reads=0; alt=[]
    for q,(pid,ln,s) in best.items():
        m=re.search(r"size=(\d+)",q); size=int(m.group(1)) if m else 1
        lin=lineage(s); g=lin.get("g","(none)"); sp=lin.get("s","(none)")
        genus[g]+=size; genus_uniq[g]+=1; reads+=size
        if "Alternaria" in g or "Alternaria" in sp:
            alt.append((acc,q,pid,ln,sp,size))
    return dict(nuniq=len(best),reads=reads,genus=genus,genus_uniq=genus_uniq,alt=alt)

R={a:parse(a) for a in ORDER}

# SUMMARY.tsv
with open(f"{DST}/SUMMARY.tsv","w",newline="") as fh:
    w=csv.writer(fh,delimiter="\t")
    w.writerow(["run","species","family","d28_alternaria_call","total_reads","baited_reads",
                "unique_baited","itsx_ITS1","itsx_ITS2","confident_fungal_unique",
                "confident_fungal_readsupport","alternaria_unique_ITS","alternaria_call"])
    for a in ORDER:
        r=R[a]; m=REC[a]
        w.writerow([a,m["species"],m["family"],m["d28"],m["total_reads"],m["baited"],
                    m["unique"],m["its1"],m["its2"],r["nuniq"],r["reads"],
                    len(r["alt"]),"PRESENT" if r["alt"] else "absent"])

# genus_table.tsv (long)
with open(f"{DST}/genus_table.tsv","w",newline="") as fh:
    w=csv.writer(fh,delimiter="\t"); w.writerow(["run","genus","read_support","n_unique_ITS"])
    for a in ORDER:
        for g,c in R[a]["genus"].most_common():
            w.writerow([a,g,c,R[a]["genus_uniq"][g]])

# alternaria_hits.tsv
with open(f"{DST}/alternaria_hits.tsv","w",newline="") as fh:
    w=csv.writer(fh,delimiter="\t"); w.writerow(["run","query_id","pct_identity","aln_len_bp","unite_species","read_size"])
    for a in ORDER:
        for row in sorted(R[a]["alt"],key=lambda x:-x[2]):
            w.writerow(list(row))

print("wrote SUMMARY.tsv, genus_table.tsv, alternaria_hits.tsv to", DST)
for a in ORDER:
    print(f"  {a}: confident_fungal={R[a]['nuniq']}  alternaria={len(R[a]['alt'])}")
