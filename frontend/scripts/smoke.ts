import { describeResult, FRONTEND_URL, smokeTest } from './local'

const baseUrl = process.argv[2] ?? FRONTEND_URL

try {
  const result = await smokeTest(baseUrl)
  console.log(`OK  ${describeResult(result)}`)
  if (result.job.status !== 'done') process.exit(1)
} catch (error) {
  console.error(`FAIL  ${error instanceof Error ? error.message : error}`)
  process.exit(1)
}
