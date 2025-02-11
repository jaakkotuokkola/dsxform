#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <stdbool.h>
#include <ctype.h>

// This C code will tokenize a regex pattern, parse it into an abstract syntax tree (AST),
// then generates random data based on the nodes in the AST.
// Currently supports a subset of regex features, expanding later should be straightforward.

// gcc -shared -o librandomvalues.so -fPIC randomvalues.c

// Token types and structure
typedef enum {
    TOKEN_LITERAL,
    TOKEN_CHAR_CLASS,
    TOKEN_QUANTIFIER,
    TOKEN_ESCAPE,
    TOKEN_ANY_CHAR,
    TOKEN_START,
    TOKEN_END,
    TOKEN_ALTERNATION,
    TOKEN_GROUP
} TokenType;

typedef struct {
    TokenType type;
    char value[256];
    int min;
    int max;
    bool is_negated;
} Token;

// AST node types and structure
typedef enum {
    AST_LITERAL,
    AST_CHAR_CLASS,
    AST_QUANTIFIER,
    AST_ESCAPE,
    AST_ANY_CHAR,
    AST_START,
    AST_END,
    AST_ALTERNATION,
    AST_GROUP
} ASTNodeType;

typedef struct ASTNode {
    ASTNodeType type;
    char value[256];
    int min;
    int max;
    bool is_negated;
    struct ASTNode* children;
    int num_children;
} ASTNode;

char random_char_in_range(char start, char end) {
    return start + (rand() % (end - start + 1));
}

char random_digit() {
    return '0' + (rand() % 10);
}

char random_lowercase() {
    return 'a' + (rand() % 26);
}

char random_uppercase() {
    return 'A' + (rand() % 26);
}

char random_alphanumeric() {
    if (rand() % 2 == 0) {
        return random_lowercase();
    } else {
        return random_digit();
    }
}

char random_whitespace() {
    char whitespace_chars[] = {' ', '\t', '\n', '\r'};
    return whitespace_chars[rand() % 4];
}

int tokenize(const char* pattern, Token** tokens, int* num_tokens) {
    *tokens = (Token*)malloc(256 * sizeof(Token));
    if (*tokens == NULL) {
        return -1; // failed to allocate memory
    }

    int token_index = 0;
    int pattern_index = 0;

    while (pattern[pattern_index] != '\0') {
        if (pattern[pattern_index] == '\\') {
            // escape sequences
            pattern_index++;
            (*tokens)[token_index].type = TOKEN_ESCAPE;
            (*tokens)[token_index].value[0] = pattern[pattern_index];
            (*tokens)[token_index].value[1] = '\0';
            token_index++;
            pattern_index++;
        } else if (pattern[pattern_index] == '[') {
            // character classes
            pattern_index++;
            (*tokens)[token_index].type = TOKEN_CHAR_CLASS;
            (*tokens)[token_index].is_negated = (pattern[pattern_index] == '^');
            if ((*tokens)[token_index].is_negated) {
                pattern_index++;
            }
            int value_index = 0;
            while (pattern[pattern_index] != ']') {
                (*tokens)[token_index].value[value_index++] = pattern[pattern_index++];
            }
            (*tokens)[token_index].value[value_index] = '\0';
            token_index++;
            pattern_index++;
        } else if (pattern[pattern_index] == '{') {
            // quantifiers
            pattern_index++; // skip '{'
            (*tokens)[token_index].type = TOKEN_QUANTIFIER;
            
            // extract quantifier content
            char buffer[32];
            int buffer_index = 0;
            while (pattern[pattern_index] != '}' && pattern[pattern_index] != '\0') {
                buffer[buffer_index++] = pattern[pattern_index++];
            }
            buffer[buffer_index] = '\0';
            
            // parse min and max values
            if (strchr(buffer, ',') != NULL) {
                // format: {m,n}
                sscanf(buffer, "%d,%d", &(*tokens)[token_index].min, &(*tokens)[token_index].max);
            } else {
                // format: {n} for exact n matches
                sscanf(buffer, "%d", &(*tokens)[token_index].min);
                (*tokens)[token_index].max = (*tokens)[token_index].min;
            }
            
            token_index++;
            pattern_index++; // skip '}'
        } else if (pattern[pattern_index] == '.') {
            // handle any character
            (*tokens)[token_index].type = TOKEN_ANY_CHAR;
            token_index++;
            pattern_index++;
        } else if (pattern[pattern_index] == '^') {
            // handle start of string
            (*tokens)[token_index].type = TOKEN_START;
            token_index++;
            pattern_index++;
        } else if (pattern[pattern_index] == '$') {
            // handle end of string
            (*tokens)[token_index].type = TOKEN_END;
            token_index++;
            pattern_index++;
        } else if (pattern[pattern_index] == '|') {
            // handle alternation, not supported yet
            (*tokens)[token_index].type = TOKEN_ALTERNATION;
            token_index++;
            pattern_index++;
        } else if (pattern[pattern_index] == '(') {
            // handle grouping
            (*tokens)[token_index].type = TOKEN_GROUP;
            token_index++;
            pattern_index++;
        } else {
            // handle literals
            (*tokens)[token_index].type = TOKEN_LITERAL;
            (*tokens)[token_index].value[0] = pattern[pattern_index];
            (*tokens)[token_index].value[1] = '\0';
            token_index++;
            pattern_index++;
        }// add more cases, some might be included in the above cases
    }

    *num_tokens = token_index;
    return 0; // success
}

// Parse the tokens into an abstract syntax tree, nodes represent different parts of the regex pattern
int parse_tokens(Token* tokens, int num_tokens, ASTNode** root) {
    printf("Parsing tokens...\n");
    ASTNode* nodes = (ASTNode*)malloc(num_tokens * sizeof(ASTNode));
    if (!nodes) {
        return -1;
    }
    int node_count = 0;
    for (int i = 0; i < num_tokens; ) {
        printf("Procesing token %d: type=%d, value='%s'\n", i, tokens[i].type, tokens[i].value);
        if (tokens[i].type == TOKEN_QUANTIFIER) {
            printf("Skipping stray quantifier at index %d\n", i);
            // Handle stray quantifier (invalid regex)
            i++;
            continue;
        }

        ASTNode node;
        int current_token_index = i;
        node.type = (ASTNodeType)tokens[i].type;
        strcpy(node.value, tokens[i].value);
        node.min = 1;
        node.max = 1;
        node.is_negated = tokens[i].is_negated;
        node.num_children = 0;
        node.children = NULL;

        // Check if next token is a quantifier
        if (i + 1 < num_tokens && tokens[i + 1].type == TOKEN_QUANTIFIER) {
            node.min = tokens[i + 1].min;
            node.max = tokens[i + 1].max;
            printf("Token %d (value='%s') is paired with quantifier token %d (min=%d, max=%d)\n",
                   current_token_index, tokens[i].value, i + 1, tokens[i + 1].min, tokens[i + 1].max);
            i += 2;
        } else {
            printf("Token %d (value='%s') is not followed by quantifier\n", current_token_index, tokens[i].value);
            i++;
        }
        nodes[node_count++] = node;
        printf("Token %d succesfully parsed into AST node Total nodes=%d\n", current_token_index, node_count);
    }

    *root = (ASTNode*)malloc(sizeof(ASTNode));
    if (!*root) {
        free(nodes);
        return -1;
    }
    (*root)->type = AST_GROUP;
    (*root)->num_children = node_count;
    (*root)->children = (ASTNode*)malloc(node_count * sizeof(ASTNode));
    if (!(*root)->children) {
        free(nodes);
        free(*root);
        *root = NULL;
        return -1;
    }
    memcpy((*root)->children, nodes, node_count * sizeof(ASTNode));
    free(nodes);

    return 0;
}

void free_ast(ASTNode* root) {
    if (root == NULL) return;
    if (root->children != NULL) {
        free(root->children);
    }
    free(root);
}

void free_tokens(Token* tokens) {
    free(tokens);
}

// Initialize random seed
void initialize_random() {
    srand(time(NULL));
}

int generate_all_data(char** headers, char** patterns, int num_headers,
                      int rows, char*** out_data) {
    *out_data = (char**)malloc(rows * num_headers * sizeof(char*));
    if (!*out_data) return -1;

    Token** token_array = (Token**)malloc(num_headers * sizeof(Token*));
    int* token_counts = (int*)malloc(num_headers * sizeof(int));
    ASTNode** ast_array = (ASTNode**)malloc(num_headers * sizeof(ASTNode*));
    if (!token_array || !token_counts || !ast_array) return -1;

    for (int i = 0; i < num_headers; i++) {
        token_array[i] = NULL;
        token_counts[i] = 0;
        if (tokenize(patterns[i], &token_array[i], &token_counts[i]) != 0) {
            return -1;
        }
        ast_array[i] = NULL;
        if (parse_tokens(token_array[i], token_counts[i], &ast_array[i]) != 0) {
            return -1;
        }
    }

    // Generate data row by row
    for (int r = 0; r < rows; r++) {
        for (int h = 0; h < num_headers; h++) {
            char* buffer = (char*)malloc(256);
            if (!buffer) return -1;
            int output_index = 0;
            ASTNode* root = ast_array[h];
            // For each child node
            for (int i = 0; i < root->num_children; i++) {
                ASTNode* node = &root->children[i];
                int length = (node->min == node->max)
                    ? node->min
                    : node->min + (rand() % (node->max - node->min + 1));
                for (int j = 0; j < length && output_index < 255; j++) {
                    switch (node->type) {
                        case AST_LITERAL:
                            buffer[output_index++] = node->value[0];
                            break;
                        case AST_CHAR_CLASS:
                            if (node->is_negated) {
                                char c;
                                do {
                                    c = random_char_in_range(' ', '~');
                                } while (strchr(node->value, c) != NULL);
                                buffer[output_index++] = c;
                            } else {
                                char start = node->value[0];
                                char end = node->value[2];
                                buffer[output_index++] = random_char_in_range(start, end);
                            }
                            break;
                        case AST_ESCAPE:
                            switch (node->value[0]) {
                                case 'd':
                                    buffer[output_index++] = random_digit();
                                    break;
                                case 'w':
                                    buffer[output_index++] = random_alphanumeric();
                                    break;
                                case 's':
                                    buffer[output_index++] = random_whitespace();
                                    break;
                                default:
                                    buffer[output_index++] = node->value[0];
                                    break;
                            }
                            break;
                        case AST_ANY_CHAR:
                            buffer[output_index++] = random_char_in_range(' ', '~');
                            break;
                        // Handle other node types as needed
                        default:
                            break;
                    }
                }
            }
            buffer[output_index] = '\0';
            (*out_data)[r*num_headers + h] = buffer;
        }
    }

    // Free ASTs & tokens
    for (int i = 0; i < num_headers; i++) {
        free_ast(ast_array[i]);
        free_tokens(token_array[i]);
    }
    free(token_array);
    free(token_counts);
    free(ast_array);

    return 0;
}