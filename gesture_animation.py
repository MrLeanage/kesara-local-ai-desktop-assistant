"""Local optical-flow interpolation for a short photographic gesture cycle."""
import cv2,numpy as np

def prepare(frames):
    h,w=frames[0].shape[:2]
    small_w=min(180,w);small_h=max(1,round(h*small_w/w))
    gray=[]
    for frame in frames:
        rgba=cv2.resize(frame,(small_w,small_h),interpolation=cv2.INTER_AREA)
        alpha=rgba[:,:,3:4]/255.0
        rgb=(rgba[:,:,:3]*alpha+128*(1-alpha)).astype(np.uint8)
        gray.append(cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY))
    detector=cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
    flows=[]
    for i in range(len(frames)-1):
        pair=[]
        for a,b in [(i,i+1),(i+1,i)]:
            flow=detector.calc(gray[a],gray[b],None)
            flow=cv2.resize(flow,(w,h),interpolation=cv2.INTER_LINEAR)
            flow[:,:,0]*=w/small_w;flow[:,:,1]*=h/small_h
            pair.append(flow)
        flows.append(pair)
    y,x=np.mgrid[0:h,0:w].astype(np.float32)
    return flows,x,y

def interpolate(frames,prepared,position):
    i=min(len(frames)-2,max(0,int(position)));fraction=max(0,min(1,position-i))
    if fraction<.001:return frames[i].copy()
    if fraction>.999:return frames[i+1].copy()
    flows,x,y=prepared;forward,backward=flows[i]
    a=cv2.remap(frames[i],x-fraction*forward[:,:,0],y-fraction*forward[:,:,1],cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT)
    b=cv2.remap(frames[i+1],x-(1-fraction)*backward[:,:,0],y-(1-fraction)*backward[:,:,1],cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT)
    # Use one warped source to avoid double contours on small moving fingers.
    return a if fraction<.5 else b
def resize_prepared(flows,width,height):
    sh,sw=flows.shape[2:4]
    resized=[]
    for pair in flows:
        result=[]
        for flow in pair:
            f=cv2.resize(flow,(width,height),interpolation=cv2.INTER_LINEAR)
            f[:,:,0]*=width/sw;f[:,:,1]*=height/sh
            result.append(f)
        resized.append(result)
    y,x=np.mgrid[0:height,0:width].astype(np.float32)
    return resized,x,y
