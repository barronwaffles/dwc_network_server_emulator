#include <stdio.h>
#include <stdlib.h>
#include <assert.h>

int main(int argc, char **argv)
{	
	// Add any search terms here that must be replaced here.
	// WARNING: Do not forget to add a replacement term!
	char *search_terms[] = { "https://" };
	char *replacement_terms[] = { "http://" };
	
	int search_term_count = sizeof(search_terms) / sizeof(search_terms[0]);
	int replacement_term_count = sizeof(replacement_terms) / sizeof(replacement_terms[0]);
	
	FILE *file = NULL;
	char *inputFilename = NULL;
	char *outputFilename = NULL;
	unsigned char *buffer = NULL;
	size_t filesize = 0;
	int idx = 0;
	
	// Make sure anyone who modifies this program read my warning above.
	assert(search_term_count == replacement_term_count);
	
	if(argc < 2)
	{
		printf("usage: %s arm9.bin (optional: arm9_patched.bin)\n", argv[0]);
		return 0;
	}
	
	inputFilename = argv[1];
	
	// If there is more than 1 argument given, take the second one as the file to save to.
	if(argc > 2)
		outputFilename = argv[2];
	else
		outputFilename = inputFilename;
		
	file = fopen(inputFilename, "rb");
	if(!file)
	{
		printf("ERROR: Could not open %s for reading.\n", inputFilename);
		return -1;
	}
	
	fseek(file,0,SEEK_END);
	filesize = ftell(file);
	rewind(file);
	
	buffer = (unsigned char*)calloc(filesize, sizeof(unsigned char));
	if(!buffer)
	{
		printf("ERROR: Could not create buffer with a size of %d bytes.\n", filesize);
		return -2;
	}
	
	fread(buffer, 1, filesize, file);	
	fclose(file);
	
	// Search for "https://nas.nintendowifi.net" and replace it with "http://nas.nintendowifi.net"
	for(idx = 0; idx < search_term_count; idx++)
	{
		int i = 0;
		int search_term_len = strlen(search_terms[idx]);
		int replacement_term_len = strlen(replacement_terms[idx]);
		
		while(i < filesize)
		{
			if(memcmp(buffer + i, search_terms[idx], search_term_len) == 0)
			{
				// Find the end of the string so we know how many bytes to move.
				// This assumes that all results are null-terminated.
				int len = strlen(buffer + i);
				char *p = (char*)(buffer + i);
				int n = 0;
				int doReplace = 1;
				
				// Search the end of the string to find out how many null
				// bytes we have to work with, just in case we plan on overwriting
				// more than originally was there.
				while(i + len + n < filesize && p[len + n] == '\0')
					n++;
					
				// Take into account that we need at least one null-terminator at the
				// end of the string.
				n--;				
				
				if(replacement_term_len > search_term_len)
				{
					// If the replacement term is longer than the term to be replaced,
					// calculate how much free space will be left over after replacement.
					int remainingSpace = n - (replacement_term_len - search_term_len);
					
					// If the free space is less than 0 then it means it runs over the
					// final null-terminator, which would cause errors in-game.
					if(remainingSpace < 0)
						doReplace = 0;
				}
				
				if(doReplace)
				{
					// Build replacement string and do replacement.
					// This method takes into account the null-terminators, so it should be safe.					
					int newlen = len + n;
					char *b = (char*)calloc(newlen + 1, sizeof(char));
					
					memcpy(b, replacement_terms[idx], replacement_term_len);
					memcpy(b + replacement_term_len, p + search_term_len, len - search_term_len);					
					
					printf("Replaced '%s' with '%s' at 0x%08x.\n", p, b, i);
					
					memcpy(p, b, newlen);					
				}
				else
				{
					printf("Not enough free space to replace '%s' with '%s' at 0x%08x.\n", search_terms[idx], replacement_terms[idx], i);
				}
				
				i += search_term_len;
			}
			else
			{		
				i++;
			}
		}
	}
	
	file = fopen(outputFilename, "wb");
	if(!file)
	{
		printf("ERROR: Could not open %s for writing.\n", outputFilename);
		return -1;
	}
	
	fwrite(buffer, 1, filesize, file);
	fclose(file);
	
	if(buffer)
		free(buffer);

	return 0;
}
