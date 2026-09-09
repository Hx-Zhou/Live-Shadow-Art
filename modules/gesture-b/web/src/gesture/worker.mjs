let detector,canvas,ctx;
self.onmessage=async({data})=>{
 try{
  if(data.type==='init'){
   const {FilesetResolver,HandLandmarker}=await import('../../vendor/vision_bundle.mjs');
   detector=await HandLandmarker.createFromOptions(await FilesetResolver.forVisionTasks(new URL('../../vendor/wasm',self.location.href).href),{baseOptions:{modelAssetPath:new URL('../../vendor/hand_landmarker.task',self.location.href).href,delegate:'CPU'},runningMode:'VIDEO',numHands:2,minHandDetectionConfidence:.6,minHandPresenceConfidence:.6,minTrackingConfidence:.6});
   self.postMessage({type:'ready'});
  }else if(data.type==='frame'){
   const start=performance.now();
   try{
    if(!canvas){canvas=new OffscreenCanvas(data.bitmap.width,data.bitmap.height);ctx=canvas.getContext('2d');}
    ctx.drawImage(data.bitmap,0,0,canvas.width,canvas.height);
    const result=detector.detectForVideo(canvas,data.timestamp);
    self.postMessage({type:'result',timestamp:data.timestamp,inferenceMs:performance.now()-start,hands:result.landmarks.map((points,i)=>({points,hand:result.handedness[i][0].categoryName.toLowerCase(),handednessScore:result.handedness[i][0].score}))});
   }finally{data.bitmap.close();}
  }
 }catch(e){self.postMessage({type:'error',message:e.message});}
};
