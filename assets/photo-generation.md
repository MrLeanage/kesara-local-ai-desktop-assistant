# Photographic Kesara portrait

Mode: built-in image_gen edit, using the original fictional Kesara sheet as identity reference. Transparent background requested. Output: kesara-photo-sheet.png.

The generated result has four columns and three rows; the renderer uses the observed layout. All twelve faces passed local landmark detection. Registration metadata is in kesara-photo-registration.json. Original source pixels are retained; alignment, mouth/eye blending and cutout edges are handled by the application renderer.

## Final prompt

Use case: identity-preserve and style-transfer. Input reference: original fictional Kesara six-pose character. Produce a NEW production photographic facial-animation sheet of exactly this SAME fictional Sri Lankan man, same facial identity, dark hair, short beard, navy jacket and charcoal shirt. Make him look like a real photographed person, NOT a game model, plastic 3D render, illustration or beauty-filter face. Natural pores, individual hairs, soft daylight studio lighting. Exactly 3 columns x 4 rows, twelve equally sized square cells, no dividers, no text. Every cell has identical camera, scale, frontal head angle, lighting, clothing and head-and-shoulders crop; show entire hairstyle with margin, shoulders and upper chest. Genuine transparent background. Row-major cells: 0 neutral relaxed face lips gently closed eyes open; 1 same with eyelids halfway closed for blink; 2 same eyes fully closed for blink; 3 same eyes open mouth modestly open saying AH; 4 same mouth saying EE; 5 same mouth rounded OH; 6 same lips pursed OO; 7 same lips pressed together saying M; 8 same upper teeth gently touching lower lip saying F; 9 same tongue touching behind upper teeth saying L; 10 same tongue tip gently between teeth saying TH; 11 same subtle friendly closed-lip smile. Crucial: identical pose and face registration in all cells, change ONLY specified eyes or mouth. Avoid broad smiles, head turns, hands, accessories, extra people or exaggerated expressions. This is an asset for subtle realistic portrait animation.

## Landmark model

Google MediaPipe Face Landmarker: https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task

SHA256: 64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff

Used offline to prepare registration metadata. No camera access or neural face inference is needed by the portrait renderer at runtime.
