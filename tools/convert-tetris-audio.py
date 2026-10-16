#!/usr/bin/env python3
"""Prepare small-header mono PCM assets without modifying the supplied originals."""
from pathlib import Path
import argparse,array,json,subprocess,wave

ROOT=Path(__file__).resolve().parents[1]
MAPPING={
    'music':'Tetris Theme Song .wav',
    'menu':'Tetris (GB) (17)-menu_sound.wav',
    'move':'Tetris (GB) (18)-move_piece.wav',
    'rotate':'Tetris (GB) (19)-rotate_piece.wav',
    'clear':'Tetris (GB) (21)-line_clear.wav',
    'tetris':'Tetris (GB) (22)-tetris_4_lines.wav',
    'level':'Tetris (GB) (23)-level_up_jingle (V1.1).wav',
    'game_over':'Tetris (GB) (25)-game_over.wav',
    'line_fall':'Tetris (GB) (26)-piece_falling_after_line_clear.wav',
    'lock':'Tetris (GB) (27)-piece_landed.wav',
}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-dir',type=Path,default=ROOT/'local-backup/audio-originals',help='Original recordings you own or are licensed to use.')
    args=parser.parse_args()
    supplied=args.input_dir
    if not supplied.is_dir():parser.error('Provide an existing --input-dir with your own licensed WAV recordings.')
    output=ROOT/'builds/MicroPython/apps_unfrozen/games/tetris_sounds'
    output.mkdir(parents=True,exist_ok=True)
    records={}
    for event,name in MAPPING.items():
        source=supplied/(event+'.wav')
        if not source.exists():source=supplied/name
        data=subprocess.run(['ffmpeg','-v','error','-i',str(source),'-ac','1','-ar','22050','-f','s16le','-'],check=True,stdout=subprocess.PIPE).stdout
        removed=0
        if event=='music':
            samples=array.array('h',data)
            last=next((i for i in range(len(samples)-1,-1,-1) if abs(samples[i])>128),len(samples)-1)
            end=min(len(samples),last+1+220)  # Keep 10 ms after the quiet threshold.
            removed=len(samples)-end
            data=data[:end*2]
        target=output/(event+'.wav')
        with wave.open(str(target),'wb') as wav:
            wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(22050);wav.writeframes(data)
        samples=array.array('h',data)
        with wave.open(str(source),'rb') as original:
            source_info={'rate':original.getframerate(),'channels':original.getnchannels(),'bits':original.getsampwidth()*8}
        records[event]={'source':source.name,'original':source_info,'file':target.name,'frames':len(data)//2,
                        'seconds':round(len(data)/44100,4),'bytes':target.stat().st_size,
                        'peak':max(abs(v) for v in samples),
                        'quiet_tail_removed_frames':removed,
                        'loop_start_frame':0,'loop_end_frame':len(data)//2} if event=='music' else {
                        'source':source.name,'original':source_info,'file':target.name,'frames':len(data)//2,
                        'seconds':round(len(data)/44100,4),'bytes':target.stat().st_size,'peak':max(abs(v) for v in samples)}
    used=set(record['source'] for record in records.values())
    excluded=[p.name for p in sorted(supplied.glob('*.wav')) if p.name not in used]
    manifest={'format':'PCM signed 16-bit little-endian','rate':22050,'channels':1,
              'assets':records,'excluded':excluded,'notes':[
                  'The user requested skipping the near-silent music tail; the original recording is preserved.',
                  'Hold uses the menu effect because the original Game Boy game had no hold asset.',
                  'The uncertain sample, unused V1.0 jingle and multiplayer effect are not deployed.']}
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    total=sum(record['bytes'] for record in records.values())
    print('Converted',len(records),'files to mono/22050Hz/16-bit PCM:',total,'bytes.')
    print('Music:',records['music']['seconds'],'seconds;',records['music']['bytes'],'bytes.')
    print('Unused originals:',len(excluded),'; original files preserved.')

if __name__=='__main__':main()
