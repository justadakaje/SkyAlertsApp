import type { MetadataRoute } from 'next'

const BASE_URL = 'https://sky.henseler.app'

export default function sitemap(): MetadataRoute.Sitemap {
  return [
    { url: `${BASE_URL}/`, changeFrequency: 'daily', priority: 1 },
    { url: `${BASE_URL}/stats`, changeFrequency: 'daily', priority: 0.8 },
    { url: `${BASE_URL}/solar-system`, changeFrequency: 'daily', priority: 0.8 },
    { url: `${BASE_URL}/about`, changeFrequency: 'monthly', priority: 0.7 },
  ]
}
