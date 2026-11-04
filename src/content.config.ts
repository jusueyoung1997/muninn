import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

// Knowledge-base notes live in the top-level `content/` directory.
// Any `.md` file there is picked up automatically; subfolders are supported
// and become part of the note's URL path.
const notes = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './content' }),
  schema: z.object({
    title: z.string(),
    description: z.string().optional(),
    date: z.coerce.date(),
    updated: z.coerce.date().optional(),
    tags: z.array(z.string()).default([]),
    draft: z.boolean().default(false),
  }),
});

export const collections = { notes };
