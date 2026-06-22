#!/bin/bash
# Classify recovered ITS (ITSx ITS1+ITS2) against UNITE with vsearch --sintax,
# cross-check with blastn, and emit a positive-vs-negative comparison.
set -uo pipefail
PROJ=/home/harte/endophynd/endophynd
VSEARCH=$(ls $PROJ/.snakemake/conda/*/bin/vsearch | head -1)
OUT=/home/harte/endophynd_cache/cold/tmp/gbi_discovery
DB=/home/harte/endophynd_cache/db/unite
SINTAX_REF=$DB/unite_sintax.fasta
BLAST_DB=$DB/unite_blast
CUTOFF=0.80

classify_one(){
  ACC=$1
  echo "### classifying $ACC ###"
  cat "$OUT/$ACC.itsx.ITS1.fasta" "$OUT/$ACC.itsx.ITS2.fasta" 2>/dev/null > "$OUT/$ACC.its.fa"
  N=$(grep -c '^>' "$OUT/$ACC.its.fa" 2>/dev/null || echo 0)
  echo "  ITS regions (ITS1+ITS2): $N"
  [ "$N" -eq 0 ] && { echo "  no ITS to classify"; return; }
  # re-derep ITS regions with clean labels + abundance (= # distinct reads supporting)
  "$VSEARCH" --derep_fulllength "$OUT/$ACC.its.fa" --relabel "${ACC}_its" --sizeout \
     --minseqlength 50 --output "$OUT/$ACC.its_derep.fa" 2>/dev/null
  U=$(grep -c '^>' "$OUT/$ACC.its_derep.fa"); echo "  unique ITS: $U"
  "$VSEARCH" --sintax "$OUT/$ACC.its_derep.fa" --db "$SINTAX_REF" \
     --tabbedout "$OUT/$ACC.sintax.tsv" --sintax_cutoff $CUTOFF --strand both --threads 16 2>/dev/null
  # blastn cross-check (top hit, >=90% id)
  blastn -query "$OUT/$ACC.its_derep.fa" -db "$BLAST_DB" -max_target_seqs 1 \
     -perc_identity 90 -qcov_hsp_perc 60 \
     -outfmt '6 qseqid sseqid pident length' -num_threads 16 > "$OUT/$ACC.blast.tsv" 2>/dev/null
}

classify_one SRR30183952
classify_one SRR30183458

python3 - "$OUT" SRR30183952 SRR30183458 <<'PY'
import sys, re, collections
out, *accs = sys.argv[1], sys.argv[2:]
def parse(acc):
    size_by_taxon=collections.Counter(); size_by_genus=collections.Counter()
    n_fungal_reads=0; n_fungal_uniq=0; total_uniq=0
    try:
        for line in open(f"{out}/{acc}.sintax.tsv"):
            f=line.rstrip("\n").split("\t")
            if len(f)<1: continue
            q=f[0]; total_uniq+=1
            m=re.search(r"size=(\d+)", q); size=int(m.group(1)) if m else 1
            pred=f[3] if len(f)>=4 else ""
            if not pred.startswith("k:Fungi"): continue
            n_fungal_reads+=size; n_fungal_uniq+=1
            # strip bootstrap if present, keep lineage
            lin=re.sub(r"\([0-9.]+\)","",pred)
            size_by_taxon[lin]+=size
            g=re.search(r"g:([^,]+)", lin); gen=g.group(1) if g else "(unresolved genus)"
            size_by_genus[gen]+=size
    except FileNotFoundError:
        pass
    return dict(total_uniq=total_uniq, n_fungal_uniq=n_fungal_uniq,
               n_fungal_reads=n_fungal_reads, genus=size_by_genus, taxon=size_by_taxon)

R={a:parse(a) for a in accs}
print("\n"+"="*70)
print("POSITIVE vs NEGATIVE — fungal ITS discovery comparison")
print("="*70)
for a in accs:
    r=R[a]
    print(f"\n{a}:  unique_ITS={r['total_uniq']}  fungal_unique={r['n_fungal_uniq']}  "
          f"fungal_read_support={r['n_fungal_reads']}")
    print(f"  top fungal genera (by read support):")
    for gen,c in r['genus'].most_common(12):
        print(f"    {c:>7}  {gen}")
    alt=[ (t,c) for t,c in r['taxon'].items() if 'Alternaria' in t ]
    if alt:
        tot=sum(c for _,c in alt)
        print(f"  *** ALTERNARIA present: read_support={tot} ***")
PY
