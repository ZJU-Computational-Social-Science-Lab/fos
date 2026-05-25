/**
 * Video configuration for external platform embedding.
 *
 * Currently configured for Bilibili external player.
 * Set VITE_BILIBILI_VIDEO_BVID in .env to your video BV ID.
 */

export const VIDEO_CONFIG = {
  /** Bilibili player configuration */
  bilibili: {
    /** Base URL for Bilibili external player */
    baseUrl: 'https://player.bilibili.com/player.html',
    /** Video BV ID - set via VITE_BILIBILI_VIDEO_BVID */
    bvId: import.meta.env.VITE_BILIBILI_VIDEO_BVID || '',
  },
} as const;

/**
 * Check if Bilibili video is configured
 */
export function isBilibiliConfigured(): boolean {
  return Boolean(VIDEO_CONFIG.bilibili.bvId);
}

/**
 * Get the Bilibili player embed URL
 */
export function getBilibiliEmbedUrl(): string {
  const { baseUrl, bvId } = VIDEO_CONFIG.bilibili;
  return `${baseUrl}?bvid=${bvId}`;
}
