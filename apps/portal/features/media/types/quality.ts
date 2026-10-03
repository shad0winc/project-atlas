export function sourceQuality(width?: number, height?: number): string {
  if (!Number.isInteger(width) || !Number.isInteger(height) ||
      width! <= 0 || height! <= 0 || width! > 32768 || height! > 32768) {
    return "Quality unknown";
  }
  const band = width! >= 3840 || height! >= 2160 ? "4K" :
    width! >= 1280 || height! >= 720 ? "HD" : "Below HD";
  return `${band} · ${width}×${height}`;
}
