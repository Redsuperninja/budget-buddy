/** Plain-English pairing errors (sync contract v1, section 7.2). Never show raw codes or HTTP numbers. */

export type PairErrorCode =
  | 'server_unreachable'
  | 'not_home_network'
  | 'bad_host'
  | 'invalid_qr'
  | 'pairing_expired'
  | 'too_many_attempts'
  | 'bad_response'
  | 'wrong_server'
  | 'clock_skew'
  | 'update_needed'
  | 'something_wrong';

export const PAIR_MESSAGES: Record<PairErrorCode, string> = {
  server_unreachable:
    "Can't reach your computer. Make sure you're on home Wi-Fi and Budget Buddy is running on your computer.",
  not_home_network:
    'Your computer only talks to phones on your home Wi-Fi. Connect to home Wi-Fi and try again.',
  bad_host:
    "Your computer didn't recognize this connection. If your computer's network changed, pair again.",
  invalid_qr:
    "That's not a Budget Buddy code. On your computer, open Budget Buddy and click Pair a phone.",
  pairing_expired:
    'That pairing code has expired. Click Pair a phone on your computer to get a new one.',
  too_many_attempts: 'Too many tries. Wait a minute, then scan the code again.',
  bad_response: 'Something on your network got in the way. Try again on your home Wi-Fi.',
  wrong_server:
    "This isn't the computer this phone was paired with. Pair again if you've changed computers.",
  clock_skew:
    'The clock on your phone or your computer is wrong. Turn on automatic date and time on both, then try again.',
  update_needed:
    'Budget Buddy needs an update on your phone or computer so they can talk to each other.',
  something_wrong: 'Something went wrong. Try again in a minute.',
};

export class PairError extends Error {
  readonly code: PairErrorCode;
  constructor(code: PairErrorCode) {
    super(PAIR_MESSAGES[code]); // the message is fixed text, never server text
    this.name = 'PairError';
    this.code = code;
  }
}

const KNOWN_SERVER_CODES: Record<string, PairErrorCode> = {
  not_home_network: 'not_home_network',
  bad_host: 'bad_host',
  pairing_expired: 'pairing_expired',
  too_many_attempts: 'too_many_attempts',
  clock_skew: 'clock_skew',
  update_needed: 'update_needed',
};

/** Map a server error code to our own text. Unknown codes become the generic message. */
export function fromServerCode(code: unknown): PairError {
  return new PairError((typeof code === 'string' && KNOWN_SERVER_CODES[code]) || 'something_wrong');
}
