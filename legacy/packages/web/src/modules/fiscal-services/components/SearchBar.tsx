'use client';

import { Search } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';

interface SearchBarProps {
  query: string;
  onQueryChange: (query: string) => void;
  onSearch: () => void;
  placeholder?: string;
}

export const SearchBar = ({
  query,
  onQueryChange,
  onSearch,
  placeholder = 'Rechercher un service fiscal...',
}: SearchBarProps) => {
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSearch();
  };

  return (
    <form onSubmit={handleSubmit} className="w-full">
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="text"
            placeholder={placeholder}
            value={query}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => onQueryChange(e.target.value)}
            className="h-12 pl-10"
          />
        </div>
        <Button type="submit" size="lg" className="h-12">
          Rechercher
        </Button>
      </div>
    </form>
  );
};

export default SearchBar;
