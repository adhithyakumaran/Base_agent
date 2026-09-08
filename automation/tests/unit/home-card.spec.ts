import { test, expect } from '@playwright/test';

test.describe('home card locator @unit', () => {
  test('exact Stock Visibility label does not match Gold Coin card', () => {
    const pattern = /^\s*Stock Visibility\s*$/i;
    expect('Stock Visibility').toMatch(pattern);
    expect('Gold Coin Stock Visibility').not.toMatch(pattern);
    expect('  Stock Visibility  ').toMatch(pattern);
  });
});
