import argparse
import sys
import pandas as pd
import numpy as np
import subprocess
from Bio import SeqIO,SeqRecord,Seq

parser = argparse.ArgumentParser(description='Generator for SNPs from a given CSV. Fields, -i')
parser.add_argument('-i', '--input_variants_csv', metavar='csv', \
    required=True, help="variants boolean csv")
parser.add_argument('-c', '--input_coverage_csv', metavar='csv', \
    required=True, help="covg matrix csv")
parser.add_argument('-r', '--reference', metavar='fasta', \
    required=True, help='fasta to project mutations onto')
parser.add_argument('-l', '--length', metavar='length', \
    required=False, help='length of reads to generate (each end)', \
    default= 150)
parser.add_argument('-b', '--basecalls_csv',metavar='csv',required=False,help='specific ATCG mutations for the variant bool positions csv', default=None)

args=parser.parse_args()

# %%
def iter_variant(ref):
    nts=np.array(['A','T','C','G'])
    ref_idx=np.where(nts == ref)[0][0]
    return np.take(nts,ref_idx+1,mode='wrap')

def generate_fasta_name(samplename, contig_name):
    return f'sample_{samplename}_contig_{contig_name}'

def parse_ref(reference):
    ref_genome = SeqIO.parse( reference, 'fasta' )
    genome_length = 0 # init
    contig_lengths = [] # init
    contig_names = [] # init
    contig_seqs = [] # init

    for record in ref_genome: # loop through contigs
        contig_names.append(record.id)
        genome_length = genome_length + len(record)
        contig_lengths.append(len(record))
        contig_seqs.append(str(record.seq))

    # Turn into numpy arrays
    genome_length = np.asarray( genome_length, dtype=np.int_ )
    contig_names = np.asarray( contig_names, dtype=object )
    contig_lengths = np.asarray( contig_lengths, dtype=object )
    contig_seqs = np.asarray( contig_seqs, dtype=object )

    return [ contig_names, contig_lengths, genome_length, contig_seqs ]

def generate_mutated_fastas(variants_boolean_csv,refgenome,basecalls_csv=None):
    """
    Parses variant positions in the variants boolean csv and outputs a new fasta file for each sample x contig for fasta generation
    """

    parsed_variants=pd.read_csv(variants_boolean_csv,header=0,index_col=0)
    if basecalls_csv:
        basecalls = pd.read_csv(variants_boolean_csv,header=0,index_col=0).values
    contig_names, _, _, contig_seqs = parse_ref(refgenome)
    c_name_to_c_seqs=dict(zip(contig_names,contig_seqs))
    contig_pos=[x.split('_') for x in parsed_variants.columns]
    samples=parsed_variants.index
    for sample_index,sample_variants in parsed_variants.iterrows():
        sample_variants_bool = np.array(sample_variants)
        for variant_position in np.where(sample_variants_bool)[0]:
            c_name,c_seq_idx=contig_pos[variant_position]
            ref = c_name_to_c_seqs[c_name][c_seq_idx]
            if basecalls == None:
                alt = iter_variant(ref)
            else:
                alt = basecalls[sample_index,variant_position]
            c_name_to_c_seqs[c_name][c_seq_idx] = alt
        for c_name in c_name_to_c_seqs:
            seq=c_name_to_c_seqs[c_name]
            seq_to_output = SeqRecord.SeqRecord(Seq(seq), id={c_name}, description=f'Mutated contig_{c_name}')
            fasta_name=generate_fasta_name(samples[sample_index], c_name)
        SeqIO.write(seq_to_output, f'{fasta_name}.fasta', "fasta")

def generate_reads_per_contig_necessary_for_coverages(input_coverage_csv,lengths,reference):
    parsed_coverages=pd.read_csv(input_coverage_csv,header=1,index=True)
    coverages_for_sample_dict={}
    contig_names,contig_lengths,_,_=parse_ref(reference)
    total_length_readpairs=lengths*2
    for _,r in parsed_coverages.iterrows():
        samplename=r.index
        covg_total=r['Covg total']
        reads_needed_per_contig=[ (r[c_name]*covg_total*c_length)/total_length_readpairs for c_name,c_length in zip(contig_names,contig_lengths) ]
        for index,value in enumerate(reads_needed_per_contig):
            fasta_name=generate_fasta_name(samplename, contig_names[index])
            coverages_for_sample_dict[f'{fasta_name}'] = value
    return coverages_for_sample_dict

def generate_reads_from_fasta(samplename, length, num_reads):
    subprocess.run([f"wgsim -N {num_reads} -R 0 -1 {length} -2 {length} {samplename}.fasta {samplename}_R1.fq {samplename}_R2.fq"],shell=True)

def main(input_variants_csv,input_coverage_csv,input_basecalls_csv,length,reference):
    generate_mutated_fastas(input_variants_csv, reference,input_basecalls_csv)
    coverages_for_samples_dict = generate_reads_per_contig_necessary_for_coverages(input_coverage_csv,length,reference)
    for sample_contig_to_output in coverages_for_samples_dict:
        num_reads=coverages_for_samples_dict[sample_contig_to_output]
        generate_reads_from_fasta(sample_contig_to_output, length, num_reads)

if __name__ == '__main__':
    main(input.input_variants_csv,input.input_coverage_csv,input.basecalls_csv,input.length,input.reference)