"""
DESCRIPTION
"""
#__author__ = "Victoria Cepeda

import os
ruleorder: kmer_mask > fastq2fasta > reference_selection > bowtie2_map > build_contigs > assembled_references >pilon_map > sam_to_bam > bam_sort > pilon_contigs >  assemble_unmapped > join_contigs > create_tsv >stats_all >stats_genome >mapping_stats

if config['reads'] != "" and config['reference'] != "%s"%expand('{outdir}/reference_selection/mc.refseq.fna',outdir=config["outdir"][0]):
     #print("%s"%(config["outdir"]))
     #print("%s"%(config["reads"]))
     #print("%s"%(config["reference"]))
     os.system("mkdir -p %s"%expand('{outdir}/reference_selection',outdir=config['outdir'])[0])
     os.system("mkdir -p %s"%expand('{outdir}/mapped_reads',outdir=config['outdir'])[0])
     os.system("mkdir -p %s"%expand('{outdir}/unmapped_reads',outdir=config['outdir'])[0])
     os.system("mkdir -p %s"%expand('{outdir}/assembly',outdir=config['outdir'])[0])
     os.system("mkdir -p %s"%expand('{outdir}/error_correction',outdir=config['outdir'])[0])
     os.system("mkdir -p %s"%expand('{outdir}/logs',outdir=config['outdir'])[0])
     os.system("mkdir -p %s"%expand('{outdir}/metacompass_output',outdir=config['outdir'])[0])

rule all:
     input:
         first=expand('{outdir}/metacompass_output/metacompass_summary.tsv',outdir=config["outdir"]),
         second=expand('{outdir}/metacompass_output/metacompass_assembly_stats.tsv',outdir=config["outdir"]),
         third=expand('{outdir}/metacompass_output/metacompass_assembly_pergenome_stats.tsv',outdir=config["outdir"]),
         fourth=expand('{outdir}/metacompass_output/metacompass_mapping_stats.tsv',outdir=config["outdir"]),
         fifth=expand('{outdir}/metacompass_output/metacompass_mapping_pergenome_stats.tsv',outdir=config["outdir"])

rule kmer_mask:
    input:
        reads=config['reads'].split(",")[0]
    output:
        fastq1=expand('{outdir}/reference_selection/marker.match.1.fastq',outdir=config['outdir'])[0],
    message: """---kmer-mask fastq"""
    params:
        out=expand('{outdir}/reference_selection/markertmp',outdir=config['outdir'])[0],
        tmp=expand('{outdir}/reference_selection/markertmp.match.1.fastq',outdir=config['outdir'])[0],
        len=str(int(config["length"])+3),
        retry='%s/reference_selection/.run1.ok'%(config['outdir'])
    threads:int(config['nthreads'])
    log:'%s/logs/kmermask.log'%(config['outdir'])
    run:

        if os.path.exists('%s/reference_selection/.run1.ok'%(config['outdir'])):
            print("Previous kmer_mask rule finished successfully. Skipping kmer_mask.")
        else:
            for read in config['reads'].split(','):
                if read != "" and len(read) != 0:
                    shell("touch {output.fastq1};kmer-mask -ms 28 -mdb %s/refseq/kmer-mask_db/markers.mdb -1 %s -clean 0.0 -match 0.01 -nomasking -t {threads} -l {params.len} -o {params.out}$RANDOM 1>> {log} 2>&1"%(config["mcdir"],read))
                    #os.system("touch {output.fastq1};kmer-mask -ms 28 -mdb %s/refseq/kmer-mask_db/markers.mdb -1 %s -clean 0.0 -match 0.01 -nomasking -t {threads} -l {params.len} -o {params.out}$RANDOM 1>> {log} 2>&1;cat {params.out}*.match.1.fastq >{output.fastq1} &&touch {params.retry}"%(config["mcdir"],read))
            shell("cat {params.out}*.match.1.fastq >{output.fastq1} && touch {params.retry}")

rule fastq2fasta:
    input: rules.kmer_mask.output.fastq1
    output:expand('{outdir}/reference_selection/masked_reads.fasta',outdir=config['outdir'],sample=config['sample'])
    message: """---Converting fastq to fasta."""
    params:
        retry='%s/reference_selection/.run2.ok'%(config['outdir'])
    log:'%s/logs/fastq2fasta.log'%(config['outdir'])
    shell : "if [[ -f {params.retry} ]]; then echo 'Previous fastq2fasta rule finished successfully. Skipping fastq2fasta.'; else %s/bin/fq2fa -i {input} -o {output} && touch {params.retry} ;fi"%(config["mcdir"])


rule reference_selection:
    input:
        fasta = rules.fastq2fasta.output,
        fastq = config['reads'].split(",")[0]
    params:
        reads=config['reads'],
        cogcov = "%d"%(int(config['cogcov'])),
        identity = "%s"%(config['ani']),
        readlen = "%d"%(int(config['length'])),
        refsel = "%s"%(config['refsel']),
        out =expand('{outdir}/reference_selection',outdir=config['outdir']),
        retry='%s/reference_selection/.run3.ok'%(config['outdir'])
    output:
        reffile =expand('{outdir}/reference_selection/mc.refseq.fna',outdir=config['outdir']),
        refids=expand('{outdir}/reference_selection/mc.refseq.ids',outdir=config['outdir'])
    message: """---reference selection."""
    threads:int(config['nthreads'])
    log:'%s/logs/reference_selection.log'%(config['outdir'])
    shell:"if [[ -f {params.retry} ]]; then echo 'Previous reference_selection rule finished successfully. Skipping reference_selection.'; else python3 %s/bin/select_references.py {params.refsel} {input.fasta} {params.reads} {params.out} {threads} {params.cogcov} {params.identity} 1>> {log} 2>&1 && touch {params.retry} ;fi"%(config["mcdir"])

rule bowtie2_map:
    input:
       ref=rules.reference_selection.output.reffile,#rules.mash_filter.output.reffile,
       r1=config['reads'].split(",")[0]
    output:
       index=expand('{outdir}/assembly/mc.index',outdir=config['outdir']),
       pref='%s/assembly/mc.index'%(config['outdir']),
       sam='%s/assembly/mc.sam'%(config['outdir']),
       log= '%s/logs/bowtie2map.log'%(config['outdir'])
    params:
        r1=config['reads'],
        retry='%s/assembly/.run1.ok'%(config['outdir'])   
    threads:int(config["nthreads"])
    message: """---Build index ."""
    shell:"bowtie2-build -o 3 --threads {threads} -q {input.ref} {output.pref} 1>> {output.index} 2>&1;bowtie2 -a --end-to-end --sensitive --no-unal -p {threads} -x {output.pref} -q -U {params.r1} -S {output.sam}.all > {output.log} 2>&1; python3 %s/bin/best_strata.py {output.sam}.all {output.sam}; rm {output.sam}.all && touch {params.retry}"%(config["mcdir"])

rule build_contigs:
    input:
        genome = rules.reference_selection.output.reffile,
        sam=  rules.bowtie2_map.output.sam
    params:
        pickref="%s"%(config['pickref']),
        mincov="%d"%(int(config['mincov'])),
        minlen="%d"%(int(config['minlen'])),
        outputdir='%s/assembly'%(config['outdir']),
        retry='%s/assembly/.run2.ok'%(config['outdir'])   
    output:
        contigs='%s/assembly/contigs.fasta'%(config['outdir']),
        mapped_reads='%s/assembly/selected_maps.sam'%(config['outdir'])
    log:'%s/logs/buildcontigs.log'%(config['outdir'])
    threads:1
    message: """---Build contigs ."""
    shell:"%s/bin/buildcontig -r {input.genome} -s {input.sam} -o {params.outputdir} -c {params.mincov} -l {params.minlen} -n F -b F -u F -k {params.pickref}  1>> {log} 2>&1 && touch {params.retry}"%(config["mcdir"])

rule assembled_references:
    input:
        genomes=rules.reference_selection.output.reffile,
        assembly=rules.build_contigs.output.contigs
    output:
        fna='%s/assembly/metacompass.assembled.fna'%(config['outdir']),
        ids='%s/assembly/metacompass.assembled.ids'%(config['outdir'])
    params:
        retry='%s/assembly/.run3.ok'%(config['outdir'])
    #log:'%s/logs/assembled_references.log'%(config['outdir'])
    threads:1
    message: """---Assembled references ."""
    shell:"grep '>' {input.assembly} |rev| cut -f2- -d '_'|rev|tr -d '>'|uniq > {output.ids};%s/bin/extractSeq {input.genomes} {output.ids} > {output.fna} && touch {params.retry}"%(config["mcdir"])

rule pilon_map:
    input:
       ref=rules.build_contigs.output.contigs,
       r1=config['r1'],
       r2=config['r2']
    output:
       index=expand('{outdir}/error_correction/mc.index',outdir=config['outdir']),
       pref='%s/error_correction/mc.index'%(config['outdir']),
       sam='%s/error_correction/mc.sam'%(config['outdir']),
       unmappedr1='%s/error_correction/mc.sam.unmapped.1.fq'%(config['outdir']),
       unmappedr2='%s/error_correction/mc.sam.unmapped.2.fq'%(config['outdir']),
       log='%s/logs/pilonmap.log'%(config['outdir'])
    params:
        retry='%s/error_correction/.run1.ok'%(config['outdir'])
    threads:int(config["nthreads"])
    message: """---Map reads for pilon polishing."""
    shell:"bowtie2-build --threads {threads} -q {input.ref} {output.pref} 1>> {output.index} 2>&1;bowtie2 --no-mixed --sensitive --no-unal -p {threads} -x {output.pref} -q -1 {input.r1} -2 {input.r2} -S {output.sam} --un-conc {output.sam}.unmapped.fq > {output.log} 2>&1 && touch {params.retry}"
    
rule sam_to_bam:
    input:
        sam=rules.pilon_map.output.sam
    output:
        bam = "%s.bam"%(rules.pilon_map.output.sam)
    params:
        retry='%s/error_correction/.run2.ok'%(config['outdir'])
    log:'%s/logs/samtools_sam2bam.log'%(config['outdir'])
    threads:1
    message: """---Convert sam to bam ."""
    shell:"samtools view -bS {input.sam} -o {output.bam} 1>> {log} 2>&1 && touch {params.retry}"

rule bam_sort:
    input:
        bam = rules.sam_to_bam.output.bam
    output:
        bam_sorted = "%s/error_correction/sorted.bam"%(config['outdir']),
    params:
        retry='%s/error_correction/.run3.ok'%(config['outdir'])
    log:'%s/logs/samtools_bamsort.log'%(config['outdir'])
    threads:int(config['nthreads'])
    message: """---Sort bam ."""
    shell: "samtools sort -@ {threads} {input.bam} -o %s/error_correction/sorted.bam -O bam -T $RANDOM 1>> {log} 2>&1; samtools index {output.bam_sorted} 1>> {log} 2>&1 && touch {params.retry} "%(config['outdir'])

rule pilon_contigs:
    input:
        contigs=rules.build_contigs.output.contigs,
        sam = rules.bam_sort.output.bam_sorted
    output:
        pilonctg='%s/error_correction/contigs.pilon.fasta'%(config['outdir'])
    params:
        memory="%d"%(int(config['memory'])),
        retry='%s/error_correction/.run4.ok'%(config['outdir']),
        tracks=config['tracks']
    log:'%s/logs/pilon.log'%(config['outdir'])
    threads:int(config['nthreads'])
    message: """---Pilon polish contigs ."""
#    shell:"       java -Xmx{params.memory}G -jar %s/bin/pilon-1.23.jar --flank 5 --threads {threads} --mindepth 3 --genome {input.contigs} --frags {input.sam} --output %s/error_correction/contigs.pilon --fix bases,amb --tracks --changes 1>> {log} 2>&1  && touch {params.retry}"%(config["mcdir"],config['outdir'])
    run:
        if config['tracks']  == "True":
            shell("java -Xmx{params.memory}G -jar %s/bin/pilon-1.23.jar --flank 5 --threads {threads} --mindepth 3 --genome {input.contigs} --frags {input.sam} --output %s/error_correction/contigs.pilon --fix bases,amb --tracks --changes 1>> {log} 2>&1  && touch {params.retry}"%(config["mcdir"],config['outdir']))
        else:
            shell("java -Xmx{params.memory}G -jar %s/bin/pilon-1.23.jar --flank 5 --threads {threads} --mindepth 3 --genome {input.contigs} --frags {input.sam} --output %s/error_correction/contigs.pilon --fix bases,amb  --changes 1>> {log} 2>&1  && touch {params.retry}"%(config["mcdir"],config['outdir']))
  
rule assemble_unmapped:
    input:
        r1=rules.pilon_map.output.unmappedr1,
        r2=rules.pilon_map.output.unmappedr2
    output:
        megahit_contigs='%s/assembly/megahit/final.contigs.fa'%(config['outdir'])
    params:
        retry='%s/assembly/.run4.ok'%(config['outdir'])
    threads:int(config["nthreads"])
    log: '%s/logs/megahit.log'%(config['outdir'])
    message: """---Assemble unmapped reads ."""
    shell:"if [[ -s {input.r1} || -s {input.r2} ]]; then rm -rf %s/assembly/megahit; megahit -o %s/assembly/megahit --min-count 3 --min-contig-len %d --presets meta-sensitive -t {threads} -1 {input.r1} -2 {input.r2}  1>> {log} 2>&1; else touch {output.megahit_contigs} {log}; echo 'No unmapped reads to run de novo assembly' >{log} ;fi && touch {params.retry}"%(config['outdir'],config['outdir'],int(config['minlen']))

rule join_contigs:
    input:
        mc_contigs=rules.pilon_contigs.output.pilonctg,
        mh_contigs=rules.assemble_unmapped.output.megahit_contigs
    message: """---concanenate reference-guided and de novo contigs"""
    output:
        final_contigs="%s/metacompass_output/metacompass.final.ctg.fa"%(config['outdir'])
    params:
        retry='%s/assembly/.run5.ok'%(config['outdir'])
    shell:"cat {input.mh_contigs} {input.mc_contigs} > {output.final_contigs} && touch {params.retry}"

rule create_tsv:
    input:
        contigs=rules.join_contigs.output.final_contigs,
        mc_contigs=rules.build_contigs.output.contigs,
        mc_contigs_pilon=rules.pilon_contigs.output.pilonctg,
        mg_contigs=rules.assemble_unmapped.output.megahit_contigs,
        asm_contigs=rules.assembled_references.output.fna,
        ref=rules.reference_selection.output.reffile
    params:    
        minlen="%d"%(int(config['minlen'])),
        retry='%s/metacompass_output/.run1.ok'%(config['outdir'])
    message: """---information reference-guided and de novo contigs"""
    output:
        summary="%s/metacompass_output/metacompass_summary.tsv"%(config['outdir']),
    shell:"sh %s/bin/create_tsv.sh {input.mc_contigs_pilon} {input.mc_contigs} {input.mg_contigs} {input.asm_contigs} {input.ref} {output.summary} && touch {params.retry}"%(config["mcdir"])
        
rule stats_all:
    input:
        contigs=rules.join_contigs.output.final_contigs,
        mc_contigs=rules.build_contigs.output.contigs,
        mc_contigs_pilon=rules.pilon_contigs.output.pilonctg,
        mg_contigs=rules.assemble_unmapped.output.megahit_contigs,
        ref=rules.reference_selection.output.reffile
    params:    
        minlen="%d"%(int(config['minlen'])),
        out='%s/assembly'%(config['outdir']),
        retry='%s/metacompass_output/.run2.ok'%(config['outdir'])
    message: """---assembly stats reference-guided contigs"""
    output:
        stats="%s/metacompass_output/metacompass_assembly_stats.tsv"%(config['outdir']),
    shell:"python3 %s/bin/assembly_stats.py {input.contigs} {params.minlen} > {output.stats} && touch {params.retry}"%(config["mcdir"])
    
rule stats_genome:
    input:
        contigs=rules.join_contigs.output.final_contigs,
        mc_contigs=rules.build_contigs.output.contigs,
        mc_contigs_pilon=rules.pilon_contigs.output.pilonctg,
        mg_contigs=rules.assemble_unmapped.output.megahit_contigs
    params:
        path="%s"%(config["mcdir"]),
        out="%s"%(config['outdir']),
        assembly="assembly",
        minlen="%d"%(int(config['minlen'])),
        log='%s/logs/statspercontig.log'%(config['outdir']),
        retry='%s/metacompass_output/.run3.ok'%(config['outdir'])
    message: """---assembly stats per genome in reference-guided contigs"""
    output:
        statspercontig="%s/metacompass_output/metacompass_assembly_pergenome_stats.tsv"%(config['outdir'])
    shell:"sh %s/bin/assembly_percontig_stats.sh {params.path} {params.out} {params.assembly} {input.mc_contigs_pilon} {params.minlen}  > {output.statspercontig} && touch {params.retry}"%(config["mcdir"])

rule mapping_stats:
    input:
        references=rules.reference_selection.output.refids,
        assembled_references=rules.assembled_references.output.ids,
        bowtie2reads= rules.bowtie2_map.output.log,# '%s/bowtie2map.log'%(config['outdir']),
        bowtie2contigs=rules.pilon_map.output.log,#'%s/pilonmap.log'%(config['outdir']),
        bowtie2sam=rules.build_contigs.output.mapped_reads#'%s/assembly/selected_maps.sam'%(config['outdir'])
    message: """---mapping stats per genome in reference-guided contigs"""
    log: '%s/mapping_stats.log'%(config['outdir'])
    output:
        mapping="%s/metacompass_output/metacompass_mapping_stats.tsv"%(config['outdir']),
        mappingpergenome="%s/metacompass_output/metacompass_mapping_pergenome_stats.tsv"%(config['outdir'])
    params:
        retry='%s/metacompass_output/.run4.ok'%(config['outdir'])
    shell:"sh %s/bin/mapping_stats.sh {input.references} {input.assembled_references} {input.bowtie2reads} {input.bowtie2contigs} {input.bowtie2sam} {output.mapping} {output.mappingpergenome} && touch {params.retry}"%(config["mcdir"])

onsuccess:
    print("MetaCompass finished successfully!")
    os.system("touch %s/.run.ok"%(config['outdir']))

#onerror:
#    print("One or more errors occurred. See MetaCompass Log files for more info")
#    sys.exit(1)