# Local avatar renderer
TalkingHead 1.7.0: Mika Suominen, MIT. Source: https://github.com/met4citizen/TalkingHead ; license in LICENSE.
Three.js 0.180.0: MIT; license in vendor/LICENSE.
AvatarSDK sample avatarsdk.glb: personal non-commercial example from TalkingHead. Source and terms: https://github.com/met4citizen/TalkingHead#test-app . Replace this sample with your own appropriately licensed rig for redistribution or commercial deployment.
Unused MPFB sample mpfb.glb: CC0, created with Blender / MPFB by the TalkingHead project.
MediaPipe hand landmarker: Google MediaPipe; official model https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task ; SHA256 fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1 . Documentation: https://developers.google.com/edge/mediapipe/solutions/vision/hand_landmarker/python .
All runtime rendering, speech recognition and gesture analysis run locally. No cloud TTS or LLM is used by the renderer.

RobotExpressive.glb: Tomás Laulhé (Quaternius), modifications by Don McCurdy, CC0. Downloaded from the Three.js r180 example asset: https://github.com/mrdoob/three.js/tree/r180/examples/models/gltf/RobotExpressive . Authored clips are rendered to a local frame cache for low-overhead playback; their skeleton animation is retained visually in the cached frames. Example and attribution: https://threejs.org/examples/webgl_animation_skinning_morph.html . Robot cache contains Idle, Wave, Yes, No and ThumbsUp only.
