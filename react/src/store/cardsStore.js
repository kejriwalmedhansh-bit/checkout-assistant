import { create } from 'zustand';

import { loadMyCards, saveMyCards } from '@/utils/myCards';

/** Which banks' credit cards the shopper has, asked once and kept on this
 * device (see utils/myCards.js). null until they answer. */
const useCardsStore = create((set) => ({
  answer: loadMyCards(),
  editing: false,
  save: (cards, prime) => {
    const answer = { cards, prime: !!prime };
    saveMyCards(answer);
    set({ answer, editing: false });
  },
  edit: () => set({ editing: true }),
}));

export default useCardsStore;
