// Redimensiona e comprime no celular antes de enviar: menos dados móveis e
// menos trabalho pro Orange Pi. O servidor recodifica de novo de qualquer jeito.

export const MAX_SIDE = 1600;
export const SELFIE_ASPECT = 3 / 4; // largura / altura do quadro da selfie

// Desenha um pedaço (sx, sy, sw, sh) da fonte num canvas de no máximo MAX_SIDE e gera um JPEG.
function toJpeg(source, sx, sy, sw, sh) {
  const scale = Math.min(1, MAX_SIDE / Math.max(sw, sh));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(sw * scale);
  canvas.height = Math.round(sh * scale);
  canvas.getContext("2d").drawImage(source, sx, sy, sw, sh, 0, 0, canvas.width, canvas.height);
  // JPEG e não WebP: o Safari do iPhone não gera WebP a partir do canvas.
  return new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.85));
}

// Selfie: recorta o centro do vídeo na proporção 3:4, exatamente o que o preview mostra.
// Desenha SEM espelhar: o preview é espelhado (como um espelho), mas a foto salva
// é a imagem real da câmera, igual em todos os dias.
export function captureVideo(video) {
  const vw = video.videoWidth, vh = video.videoHeight;
  let sw = vw, sh = vh;
  if (vw / vh > SELFIE_ASPECT) sw = vh * SELFIE_ASPECT; // vídeo mais largo: corta as laterais
  else sh = vw / SELFIE_ASPECT;                        // mais alto: corta em cima e embaixo
  return toJpeg(video, (vw - sw) / 2, (vh - sh) / 2, sw, sh);
}

// Foto da galeria (extra): só reduz, respeitando a rotação gravada no EXIF.
export async function resizeFile(file) {
  const bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
  try {
    return await toJpeg(bitmap, 0, 0, bitmap.width, bitmap.height);
  } finally {
    bitmap.close();
  }
}
