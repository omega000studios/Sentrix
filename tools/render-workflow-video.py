"""Render an illustrated Sentrix walkthrough with Pillow and a local FFmpeg binary.

Run with a Python environment containing Pillow:
python tools/render-workflow-video.py --ffmpeg /path/to/ffmpeg
The video illustrates the workflow; it is not a screen recording or a live API run.
"""
import argparse
import io
from pathlib import Path
import subprocess

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT, FPS = 1280, 720, 24
DURATIONS = (5, 7, 7, 9, 7, 7, 7, 7)
BG, INK, BLUE, MUTED = '#F4F7FC', '#14243A', '#174FCD', '#53647B'
LINE, RED, GREEN, AMBER = '#D9E2EE', '#A82F40', '#236C51', '#815B09'
FONT_DIR = Path('C:/Windows/Fonts')
FONTS = {}


def font(size, bold=False):
    key = (size, bold)
    if key not in FONTS:
        FONTS[key] = ImageFont.truetype(str(FONT_DIR / ('seguisb.ttf' if bold else 'segoeui.ttf')), size)
    return FONTS[key]


def ease(value):
    return 1 - (1 - max(0, min(1, value))) ** 3


def text(draw, xy, value, size=28, color=INK, bold=False):
    draw.text(xy, value, font=font(size, bold), fill=color)


def panel(draw, box, fill='white', border=LINE):
    draw.rounded_rectangle(box, radius=10, fill=fill, outline=border, width=1)


def header(draw, step, heading, subheading, dark=False):
    ink, muted = ('white', '#B9C9DF') if dark else (INK, MUTED)
    text(draw, (58, 26), 'Sentrix', 27, '#88ADFF' if dark else BLUE, True)
    text(draw, (1000, 34), f'{step + 1:02d} / 08   WORKFLOW', 15, muted)
    draw.line((58, 78, 1222, 78), fill='#334A69' if dark else LINE, width=1)
    text(draw, (58, 110), heading, 43, ink, True)
    text(draw, (60, 173), subheading, 23, muted)


def caption(draw, value, dark=False):
    draw.line((58, 621, 1222, 621), fill='#334A69' if dark else LINE, width=1)
    text(draw, (60, 642), value, 23, '#DCE7F6' if dark else MUTED)


def connector(draw, start, end, time, delay=0):
    draw.line((*start, *end), fill=LINE, width=3)
    p = ease((time - delay) / 0.8)
    if time >= delay:
        x = start[0] + (end[0] - start[0]) * p
        y = start[1] + (end[1] - start[1]) * p
        draw.ellipse((x-7, y-7, x+7, y+7), fill=BLUE)


def address(draw, x, y, number, color=INK):
    for offset, line in enumerate((f'{number} Main Street', 'Apt 4', 'Austin, TX 78701', 'United States')):
        text(draw, (x, y + offset * 43), line, 30 if offset == 0 else 25, color if offset == 0 else MUTED, offset == 0)


def scene(index, time):
    dark = index == 5
    image = Image.new('RGB', (WIDTH, HEIGHT), '#14243A' if dark else BG)
    draw = ImageDraw.Draw(image)
    offset = int(24 * (1 - ease(time / 0.5)))
    if index == 0:
        text(draw, (60, 40), 'Sentrix', 31, BLUE, True)
        text(draw, (60, 143 + offset), 'Catch a changed', 72, INK, True)
        text(draw, (60, 230 + offset), 'shipping address.', 72, INK, True)
        text(draw, (64, 348), 'A pre-dispatch check for the merchant.', 30, MUTED)
        labels = ['PayPal payment', 'Address check', 'Merchant decision']
        for i, label in enumerate(labels):
            x = 64 + i * 396
            if i < 2:
                connector(draw, (x + 290, 492), (x + 377, 492), time, 0.9 + i * 0.8)
            panel(draw, (x, 450, x + 290, 537))
            text(draw, (x + 23, 474), label, 24, BLUE if i == 1 else INK, True)
        caption(draw, 'An illustrated walkthrough of the current build and planned integrations.')
    elif index == 1:
        header(draw, index, 'Start with the payment record.', 'The original PayPal destination stays the reference address.')
        panel(draw, (60, 244 + offset, 493, 573 + offset))
        text(draw, (90, 269 + offset), 'PayPal sandbox', 24, BLUE, True)
        text(draw, (90, 318 + offset), '$1.00', 76, INK, True)
        text(draw, (92, 421 + offset), 'Capture completed', 26, GREEN, True)
        text(draw, (92, 467 + offset), 'Eligibility returned: ELIGIBLE', 21, MUTED)
        text(draw, (92, 518 + offset), 'Verified sandbox test', 20, MUTED)
        connector(draw, (495, 403), (650, 403), time, 1.2)
        if time > 0.8:
            panel(draw, (653, 244, 1220, 573))
            text(draw, (686, 270), 'Saved payment address', 22, BLUE, True)
            address(draw, 686, 322, '123')
            text(draw, (686, 522), 'Source: sandbox • imported manually', 20, MUTED)
        caption(draw, 'The payment was completed in PayPal sandbox, then imported into Sentrix.')
    elif index == 2:
        header(draw, index, 'A customer requests a change.', 'Message text becomes structured facts for the backend.')
        panel(draw, (60, 257 + offset, 640, 553 + offset))
        text(draw, (90, 285 + offset), 'Simulated customer message', 21, MUTED)
        text(draw, (90, 351 + offset), '“Please ship to my', 39, INK, True)
        text(draw, (90, 403 + offset), 'office instead.”', 39, INK, True)
        text(draw, (90, 493 + offset), 'A change request is not proof of fraud.', 23, MUTED)
        connector(draw, (642, 405), (743, 405), time, 1.3)
        if time > 1:
            panel(draw, (746, 257, 1220, 553), '#EAF0FF')
            text(draw, (774, 286), 'AI extraction • planned', 23, BLUE, True)
            text(draw, (774, 351), 'Intent: address change', 25, INK, True)
            text(draw, (774, 403), 'Quote: “ship to my office”', 23)
            text(draw, (774, 455), 'Confidence + proposed address', 21, MUTED)
        caption(draw, 'Today, analysis is supplied as JSON. Direct AI extraction is still pending.')
    elif index == 3:
        header(draw, index, 'Compare where the parcel will go.', 'Formatting can vary. The destination must still agree.')
        panel(draw, (60, 245, 604, 543))
        panel(draw, (634, 245, 1220, 543))
        text(draw, (90, 271), 'PayPal payment address', 22, BLUE, True)
        text(draw, (664, 271), 'Simulated shipping label', 22, MUTED, True)
        reveal = ease((time - 1.3) / 0.5)
        if reveal > 0:
            draw.rounded_rectangle((652, 322, 1178, 369), radius=5, fill='#FBE5E7')
        address(draw, 90, 325, '123')
        address(draw, 664, 325, '987' if time >= 1.3 else '123', RED if time >= 1.3 else INK)
        if time > 2.5:
            text(draw, (64, 570), 'Different house number', 25, RED, True)
            text(draw, (700, 570), 'Comparison: MISMATCH', 25, RED, True)
        caption(draw, '123 and 987 are different destinations. This is more than a formatting change.')
    elif index == 4:
        header(draw, index, 'Rules decide. The merchant acts.', 'AI extracts information; deterministic code produces the verdict.')
        rows = [('PROTECTED', 'Supported addresses agree and checks pass.', GREEN), ('REVIEW', 'Missing data, low confidence, or uncertain eligibility.', AMBER), ('BLOCKED', 'Reliable inputs show a different destination.', RED)]
        for i, (name, meaning, color) in enumerate(rows):
            p = ease((time - i * 0.8) / 0.4)
            if p > 0:
                y = int(251 + i * 107 + 15 * (1-p))
                panel(draw, (60, y, 1220, y+87), '#FBE5E7' if i == 2 and time > 2.7 else 'white')
                draw.ellipse((85, y+36, 99, y+50), fill=color)
                text(draw, (116, y+24), name, 28, color, True)
                text(draw, (390, y+29), meaning, 24, INK)
        caption(draw, 'BLOCKED records a hold decision. It does not stop a carrier or freeze PayPal funds.')
    elif index == 5:
        header(draw, index, 'Keep the facts behind the decision.', 'Every verdict has an input snapshot, reasons, time, and rule version.', True)
        events = [('Payment captured', 'Original address retained', '#8BB0FF'), ('Matching label checked', 'PROTECTED', '#8DD4B4'), ('House number changed', 'BLOCKED • Different number', '#FFB1BA')]
        draw.line((90, 281, 90, 546), fill='#405672', width=2)
        for i, (label, value, color) in enumerate(events):
            if time > i * 0.9:
                y = 265+i*105
                draw.ellipse((82,y+9,98,y+25), fill=color)
                text(draw,(122,y),label,28,'white',True)
                text(draw,(122,y+42),value,23,color)
        if time > 2.8:
            panel(draw,(808,271,1220,557),'#1D3451','#405672')
            text(draw,(838,301),'Saved audit history',27,'white',True)
            for i,line in enumerate(['Payment address','Latest label inputs','Comparison + reasons','Rule version + time']):
                text(draw,(838,361+i*41),line,23,'#C5D5EB')
        caption(draw, 'Database persistence and rollback were checked on Postgres.', True)
    elif index == 6:
        header(draw,index,'One queue for the merchant.','Open an order, compare addresses, and read the reason before dispatch.')
        panel(draw,(60,240,1220,582))
        draw.rectangle((61,241,1219,288),fill='#EAF0FF')
        text(draw,(82,251),'Sentrix / Dispatch queue',21,BLUE,True)
        text(draw,(953,254),'Illustrated dashboard',17,MUTED)
        labels = [('Sandbox payment','$1.00','Blocked',RED),('Clean fixture','$149.99','Protected',GREEN),('Uncertain fixture','$149.99','Review',AMBER)]
        for i,(name,amount,result,color) in enumerate(labels):
            y=319+i*76
            if i == 0: draw.rectangle((61,y-6,711,y+56),fill='#F0F5FF')
            text(draw,(85,y),name,23,INK,i==0)
            text(draw,(365,y),amount,22)
            text(draw,(540,y),result,22,color,True)
            draw.line((80,y+57,693,y+57),fill=LINE)
        draw.line((723,289,723,581),fill=LINE)
        text(draw,(752,314),'Hold dispatch',29,RED,True)
        text(draw,(752,367),'PayPal: 123 Main Street',23)
        text(draw,(752,411),'Label:   987 Main Street',23,RED,True)
        text(draw,(752,472),'Reason: Different number',23,MUTED)
        caption(draw,'The local dashboard is connected. Label checks in the demo are simulated.')
    else:
        header(draw,index,'Working today. Connected next.','A tested backend, with the remaining integrations clearly separated.')
        draw.line((634,252,634,573),fill=LINE,width=2)
        text(draw,(64,247),'Verified',29,GREEN,True)
        text(draw,(686,247),'Next integrations',29,BLUE,True)
        for i,line in enumerate(['$1 PayPal sandbox capture','Manual import + address verdicts','Saved audit records','43 tests passed, 1 expected skip']):
            text(draw,(65,313+i*52),line,25)
        for i,line in enumerate(['Verified PayPal webhooks','Actual AI message + label extraction','Hosted backend and dashboard','Approved actions + evidence bundles']):
            text(draw,(687,313+i*52),line,23)
        caption(draw,'Sentrix helps the merchant catch a destination mismatch before shipment.')
    draw.rectangle((0,HEIGHT-5,int(WIDTH*(sum(DURATIONS[:index])+time)/sum(DURATIONS)),HEIGHT),fill=BLUE)
    return image


def frame(time):
    start=0
    for index,duration in enumerate(DURATIONS):
        if time < start+duration:
            local=time-start
            image=scene(index,local)
            if index < len(DURATIONS)-1 and local > duration-0.35:
                image=Image.blend(image,scene(index+1,0),ease((local-duration+0.35)/0.35))
            return image
        start+=duration
    return scene(len(DURATIONS)-1,DURATIONS[-1]-1/FPS)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ffmpeg',required=True)
    args=parser.parse_args()
    out=Path('output/video')
    out.mkdir(parents=True,exist_ok=True)
    # Check caption bounds and easing before spending time encoding.
    assert ease(0)==0 and ease(1)==1 and 0 < ease(0.5) < 1
    assert all(a > 0 for a in DURATIONS)
    samples=[2,8,15,24,32,38,45,52]
    for i,t in enumerate(samples):
        image=frame(t)
        assert image.size==(WIDTH,HEIGHT)
        image.save(out/f'preview-{i+1}.png')
    frame(24).save(out/'sentrix-workflow-poster.png')
    target=out/'sentrix-workflow.webm'
    command=[args.ffmpeg,'-y','-hide_banner','-loglevel','error','-f','image2pipe','-c:v','mjpeg','-framerate',str(FPS),'-i','pipe:0','-an','-c:v','libvpx-vp9','-deadline','realtime','-cpu-used','6','-threads','4','-b:v','1400k','-pix_fmt','yuv420p',str(target)]
    with (out/'encode.log').open('wb') as log:
        process=subprocess.Popen(command,stdin=subprocess.PIPE,stderr=log)
        try:
            for n in range(sum(DURATIONS)*FPS):
                buffer=io.BytesIO()
                frame(n/FPS).save(buffer,format='JPEG',quality=91)
                process.stdin.write(buffer.getvalue())
                if n % (FPS*7)==0: print(f'Rendering {n//FPS}/{sum(DURATIONS)} seconds',flush=True)
            process.stdin.close()
            if process.wait()!=0: raise RuntimeError('FFmpeg failed; see output/video/encode.log')
        except BaseException:
            process.kill()
            process.wait()
            raise
    assert target.stat().st_size > 10000
    print(f'Created {target.resolve()} ({sum(DURATIONS)}s, {WIDTH}x{HEIGHT}, {FPS}fps)',flush=True)


if __name__=='__main__':
    main()
