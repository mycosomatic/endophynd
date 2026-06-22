#!/usr/bin/env python3
"""Aggregate confident fungal ITS (blastn >=90% id, >=60% qcov vs UNITE) per dataset
and compare positive vs negative. Discriminator = BLAST to fungal DB (NOT sintax
k:Fungi, which is meaningless against a Fungi-only reference)."""
import re, collections, sys

OUT="/home/harte/endophynd_cache/cold/tmp/gbi_discovery"
DATASETS=[("SRR30183952","Silene_verecunda (D28 ALTERNARIA-POSITIVE)"),
          ("SRR30183458","Streptanthus_glandulosus (D28 ALTERNARIA-NEGATIVE)")]

def lineage(sseqid):
    # Name|ACC|SH|type|k__Fungi;p__...;g__Genus;s__Species
    parts=sseqid.split("|")
    tax=parts[4] if len(parts)>=5 else ""
    d={}
    for f in tax.split(";"):
        if "__" in f:
            r,v=f.split("__",1); d[r]=v
    return d

def parse(acc):
    best={}  # qseqid -> (pident, length, sseqid)  keep best pident per query
    for line in open(f"{OUT}/{acc}.blast.tsv"):
        f=line.rstrip("\n").split("\t")
        if len(f)<4: continue
        q,s,pid,ln=f[0],f[1],float(f[2]),int(f[3])
        if q not in best or pid>best[q][0]:
            best[q]=(pid,ln,s)
    genus=collections.Counter(); genus_uniq=collections.Counter()
    species=collections.Counter()
    reads=0; alt_rows=[]
    pid_hist=collections.Counter()
    for q,(pid,ln,s) in best.items():
        m=re.search(r"size=(\d+)",q); size=int(m.group(1)) if m else 1
        lin=lineage(s); g=lin.get("g","(none)"); sp=lin.get("s","(none)")
        genus[g]+=size; genus_uniq[g]+=1; species[sp]+=size; reads+=size
        pid_hist[">=97" if pid>=97 else (">=95" if pid>=95 else ">=90")]+=size
        if "Alternaria" in g or "Alternaria" in sp:
            alt_rows.append((q,pid,ln,sp,size))
    return dict(nuniq=len(best),reads=reads,genus=genus,genus_uniq=genus_uniq,
                species=species,alt=alt_rows,pid=pid_hist)

R={a:parse(a) for a,_ in DATASETS}

print("="*78)
print("CONFIDENT FUNGAL ITS  (blastn >=90% id, >=60% qcov vs UNITE 10.0; ITSx ITS1+ITS2)")
print("="*78)
for a,lab in DATASETS:
    r=R[a]
    print(f"\n### {a}  —  {lab}")
    print(f"  confident fungal ITS: unique={r['nuniq']}  read_support={r['reads']}")
    print(f"  identity tiers (read_support): "
          + "  ".join(f"{k}={r['pid'][k]}" for k in (">=97",">=95",">=90") if r['pid'][k]))
    print(f"  top fungal genera (read_support | #unique):")
    for g,c in r['genus'].most_common(15):
        print(f"     {c:>6} | {r['genus_uniq'][g]:>4}  {g}")

print("\n"+"="*78)
print("ALTERNARIA verdict (the D28 contrast)")
print("="*78)
for a,lab in DATASETS:
    r=R[a]; alt=r['alt']
    if alt:
        tot=sum(x[4] for x in alt); pids=sorted({round(x[1],1) for x in alt})
        print(f"  {a} ({lab.split(' ')[0]}): ALTERNARIA PRESENT — "
              f"{len(alt)} unique ITS, read_support={tot}, identity={pids}")
        for q,pid,ln,sp,size in sorted(alt,key=lambda x:-x[4])[:5]:
            print(f"        {q}  {pid}% / {ln}bp  -> {sp}  (size {size})")
    else:
        print(f"  {a} ({lab.split(' ')[0]}): no Alternaria among confident fungal ITS")
