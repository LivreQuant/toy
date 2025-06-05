export class ConvictionsApi {
    constructor(client) {
        this.client = client;
    }
    async submitConvictions(submissionData) {
        const formData = new FormData();
        // Add the bookId
        formData.append('bookId', submissionData.bookId);
        // Add the convictions as a JSON blob
        formData.append('convictions', JSON.stringify(submissionData.convictions));
        // Add research file if provided
        if (submissionData.researchFile) {
            formData.append('researchFile', submissionData.researchFile);
        }
        // Add notes if provided
        if (submissionData.notes) {
            formData.append('notes', submissionData.notes);
        }
        return this.client.postMultipart('/convictions/submit', formData);
    }
    async cancelConvictions(cancellationData) {
        const formData = new FormData();
        // Add the bookId
        formData.append('bookId', cancellationData.bookId);
        // Add the conviction IDs as a JSON array
        formData.append('convictionIds', JSON.stringify(cancellationData.convictionIds));
        // Add research file if provided
        if (cancellationData.researchFile) {
            formData.append('researchFile', cancellationData.researchFile);
        }
        // Add notes if provided
        if (cancellationData.notes) {
            formData.append('notes', cancellationData.notes);
        }
        return this.client.postMultipart('/convictions/cancel', formData);
    }
    // New encoded fingerprint methods
    async submitConvictionsEncoded(submissionData) {
        return this.client.post('/convictions/encoded_submit', {
            bookId: submissionData.bookId,
            convictions: submissionData.convictions,
            researchFile: submissionData.researchFile,
            notes: submissionData.notes
        });
    }
    async cancelConvictionsEncoded(cancellationData) {
        return this.client.post('/convictions/encoded_cancel', {
            bookId: cancellationData.bookId,
            convictionIds: cancellationData.convictionIds,
            researchFile: cancellationData.researchFile,
            notes: cancellationData.notes
        });
    }
}
