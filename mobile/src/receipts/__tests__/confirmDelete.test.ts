import { Alert } from 'react-native';

import { confirmDelete, deleteQuestion } from '../confirmDelete';

describe('deleteQuestion', () => {
  it('asks about one receipt', () => {
    expect(deleteQuestion(1)).toMatchObject({ title: 'Delete this receipt?', action: 'Delete' });
  });
  it('says how many go when clearing', () => {
    expect(deleteQuestion(3).message).toContain('all 3 waiting receipts');
    expect(deleteQuestion(null).message).toContain('all the waiting receipts');
  });
});

describe('confirmDelete', () => {
  it('deletes only after the person agrees', () => {
    const spy = jest.spyOn(Alert, 'alert').mockImplementation(() => undefined);
    const onConfirm = jest.fn();
    confirmDelete(1, onConfirm);
    expect(onConfirm).not.toHaveBeenCalled();
    const buttons = spy.mock.calls[0][2] as { text: string; onPress?: () => void }[];
    expect(buttons[0].text).toBe('Keep');
    buttons[1].onPress?.();
    expect(onConfirm).toHaveBeenCalledTimes(1);
    spy.mockRestore();
  });
});
