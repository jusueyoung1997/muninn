// @ts-check
import { defineConfig } from 'astro/config';
import { unified } from '@astrojs/markdown-remark';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';

// Set SITE_URL in Cloudflare's build variables once the public URL is known.
// Leaving it unset supports local development and the first static deployment.
export default defineConfig({
  site: process.env.SITE_URL || undefined,
  base: '/',
  output: 'static',
  srcDir: './src',
  markdown: {
    processor: unified({
      remarkPlugins: [remarkMath],
      rehypePlugins: [[rehypeKatex, { strict: 'error' }]],
    }),
  },
});
