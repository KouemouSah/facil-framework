'use client';

import { useState, useCallback } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Upload, File, X, CheckCircle, AlertCircle } from 'lucide-react';
import { formatFileSize } from '@/core/utils';

interface DocumentUploadProps {
  onUpload: (files: File[]) => Promise<void>;
  maxSize?: number; // MB
  acceptedTypes?: string[];
}

export const DocumentUpload = ({
  onUpload,
  maxSize = 10,
  acceptedTypes = ['.pdf', '.doc', '.docx', '.jpg', '.jpeg', '.png'],
}: DocumentUploadProps) => {
  const [files, setFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const handleFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const selectedFiles = Array.from(e.target.files || []);
      const validFiles = selectedFiles.filter((file) => {
        if (file.size > maxSize * 1024 * 1024) {
          setError(`Le fichier ${file.name} dépasse ${maxSize}MB`);
          return false;
        }
        return true;
      });
      setFiles((prev) => [...prev, ...validFiles]);
      setError(null);
    },
    [maxSize]
  );

  const removeFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleUpload = async () => {
    if (files.length === 0) return;

    try {
      setUploading(true);
      setError(null);
      await onUpload(files);
      setSuccess(true);
      setFiles([]);
      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Échec du téléversement');
    } finally {
      setUploading(false);
    }
  };

  return (
    <Card className="p-6">
      <div className="space-y-4">
        <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center hover:border-primary transition-colors">
          <Upload className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
          <p className="text-sm text-muted-foreground mb-2">
            Glissez-déposez vos fichiers ou cliquez pour sélectionner
          </p>
          <input
            type="file"
            multiple
            accept={acceptedTypes.join(',')}
            onChange={handleFileChange}
            className="hidden"
            id="file-upload"
          />
          <Button asChild variant="outline">
            <label htmlFor="file-upload" className="cursor-pointer">
              Sélectionner des fichiers
            </label>
          </Button>
          <p className="text-xs text-muted-foreground mt-2">
            Formats acceptés: {acceptedTypes.join(', ')} (max {maxSize}MB)
          </p>
        </div>

        {files.length > 0 && (
          <div className="space-y-2">
            <h4 className="font-semibold text-sm">Fichiers sélectionnés:</h4>
            {files.map((file, index) => (
              <div
                key={index}
                className="flex items-center justify-between p-3 bg-muted rounded-lg"
              >
                <div className="flex items-center gap-3">
                  <File className="h-5 w-5 text-primary" />
                  <div>
                    <p className="text-sm font-medium">{file.name}</p>
                    <p className="text-xs text-muted-foreground">{formatFileSize(file.size)}</p>
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => removeFile(index)}
                  disabled={uploading}
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            ))}
          </div>
        )}

        {error && (
          <div className="flex items-center gap-2 p-3 bg-destructive/10 text-destructive rounded-lg">
            <AlertCircle className="h-4 w-4" />
            <span className="text-sm">{error}</span>
          </div>
        )}

        {success && (
          <div className="flex items-center gap-2 p-3 bg-green-100 text-green-700 rounded-lg">
            <CheckCircle className="h-4 w-4" />
            <span className="text-sm">Fichiers téléversés avec succès!</span>
          </div>
        )}

        <Button
          onClick={handleUpload}
          disabled={files.length === 0 || uploading}
          className="w-full"
        >
          {uploading ? 'Téléversement...' : `Téléverser ${files.length} fichier(s)`}
        </Button>
      </div>
    </Card>
  );
};

export default DocumentUpload;
