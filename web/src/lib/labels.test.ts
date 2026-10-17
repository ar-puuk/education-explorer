import { describe, expect, it } from 'vitest'
import { gradeLabel, levelLabel, localeLabel, schoolYearLabel } from './labels'

describe('labels', () => {
  it('formats school years', () => {
    expect(schoolYearLabel(2024)).toBe('2024-25')
    expect(schoolYearLabel(1999)).toBe('1999-00')
  })
  it('merges spellings of "no value" for levels', () => {
    for (const v of ['N', 'Not Reported', 'not reported', null, '']) expect(levelLabel(v)).toBe('Not reported')
    expect(levelLabel('High')).toBe('High')
  })
  it('labels grades and locales', () => {
    expect(gradeLabel('KG')).toBe('K')
    expect(gradeLabel('07')).toBe('7')
    expect(localeLabel('21')).toBe('Suburb, large')
    expect(localeLabel('99')).toBe('99')
  })
})
