import { Pipe, PipeTransform } from '@angular/core';

const formatters = new Map<string, Intl.NumberFormat>();

/** Numbers in the current page language format (pl: 0,2; en: 0.2). */
@Pipe({ name: 'aedNumber', standalone: true })
export class AedNumberPipe implements PipeTransform {
  transform(value: number | null | undefined, lang: string, digits = 0): string {
    if (value == null) {
      return '';
    }
    const key = `${lang}:${digits}`;
    if (!formatters.has(key)) {
      formatters.set(
        key,
        new Intl.NumberFormat(lang === 'en' ? 'en-GB' : 'pl-PL', {
          minimumFractionDigits: digits,
          maximumFractionDigits: digits,
        }),
      );
    }
    return formatters.get(key)!.format(value);
  }
}
