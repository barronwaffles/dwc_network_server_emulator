// Algorithm the same as used in enctypex_decoder by Luigi Auriemma, just in an easy to use single program.

int main(int argc, char **argv)
{
	int i = 0;
	unsigned int server = 0;

	if(argc != 2)
	{
		printf("usage: %s servername\n", argv[0]);
	}
	
	for(i = 0; i < strlen(argv[1]); i++)
	{
		unsigned char c = tolower(argv[1][i]);
		server = c - (server * 0x63306ce7);
	}
	server %= 20;
	
	printf("%s.ms%d.nintendowifi.net", argv[1], server);

	return 0;
}
