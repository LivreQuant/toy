// frontend/src/api/book.ts
export class BookApi {
    constructor(client) {
        this.client = client;
    }
    async createBook(bookData) {
        return this.client.post('/books', bookData);
    }
    async getBooks() {
        return this.client.get('/books');
    }
    async getBook(bookId) {
        return this.client.get(`/books/${bookId}`);
    }
    async updateBook(bookId, updates) {
        return this.client.put(`/books/${bookId}`, updates);
    }
}
