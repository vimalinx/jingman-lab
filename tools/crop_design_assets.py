"""Reproducibly crop ONLY the user's supplied design mockups. No external downloads."""
from PIL import Image,ImageOps
from pathlib import Path
import argparse
SOURCE_DIR = None
ROOT=Path(__file__).resolve().parents[1]
FILES={'home':'f4b2b557-8ca1-4e1c-a273-708418832942.png','list':'08817e6d-aedb-4807-9896-461294fc8df2.png','detail':'64cea53c-d16a-4345-956e-a76de876ee18.png','cart':'6140e460-1951-48f3-b055-2e516ac741a8.png','profile':'3192da93-4313-4347-9d7f-9aadf88d0d03.png'}
CROPS={
 'banana':('home',(72,1086,424,1299)),
 'cherry':('home',(505,1090,887,1299)),
 'strawberry':('detail',(310,180,910,565)),
 'tomato':('list',(218,399,400,554)),
 'lettuce':('list',(216,590,404,768)),
 'carrot':('list',(215,790,404,966)),
 'potato':('list',(214,992,404,1168)),
 'broccoli':('list',(216,1194,404,1365)),
 'mushroom':('list',(215,1395,404,1542)),
 'milk':('cart',(155,872,264,1046)),
 'cola':('cart',(164,1128,247,1285)),
 'snack':('home',(338,759,437,876)),
 'oil':('home',(650,759,717,876)),
 'daily':('home',(790,759,888,875)),
}

def crop(source,box):
 im=Image.open(SOURCE_DIR/FILES[source]).convert('RGB');sx=im.width/928;sy=im.height/1648
 return im.crop(tuple(round(v*(sx if i%2==0 else sy)) for i,v in enumerate(box)))

def main():
 global SOURCE_DIR
 parser=argparse.ArgumentParser(description='Regenerate bundled crops from the original user-supplied mockup images. Requires Pillow.')
 parser.add_argument('--source-dir',type=Path,required=True,help='Directory containing the original PNG filenames listed in FILES')
 parser.add_argument('--contact-sheet',type=Path,help='Optional preview JPG destination')
 args=parser.parse_args();SOURCE_DIR=args.source_dir
 for filename in FILES.values():
  if not (SOURCE_DIR/filename).is_file():parser.error('Missing source image: '+str(SOURCE_DIR/filename))
 (ROOT/'web/assets').mkdir(parents=True,exist_ok=True)
 for name,(source,box) in CROPS.items():
  im=crop(source,box)
  if name in ('strawberry',):im=ImageOps.fit(im,(512,512))
  else:
   im=ImageOps.contain(im,(460,410));canvas=Image.new('RGB',(512,512),'white');canvas.paste(im,((512-im.width)//2,(512-im.height)//2));im=canvas
  im.save(ROOT/'web/assets'/f'{name}.webp',quality=88)
 crop('home',(608,416,906,705)).save(ROOT/'web/assets/hero.webp',quality=90)
 crop('detail',(0,146,928,597)).save(ROOT/'web/assets/strawberry-detail.webp',quality=90)
 crop('profile',(34,241,168,375)).resize((180,180)).save(ROOT/'web/assets/avatar.webp',quality=90)
 tiles=Image.new('RGB',(512*5,560*3),'#f2f5f2')
 from PIL import ImageDraw
 for n,name in enumerate(CROPS):
  im=Image.open(ROOT/'web/assets'/f'{name}.webp');tiles.paste(im,((n%5)*512,(n//5)*560));ImageDraw.Draw(tiles).text(((n%5)*512+10,(n//5)*560+520),name,fill='black')
 if args.contact_sheet:
  args.contact_sheet.parent.mkdir(parents=True,exist_ok=True)
  tiles.resize((1280,840)).save(args.contact_sheet)
if __name__=='__main__':main()
