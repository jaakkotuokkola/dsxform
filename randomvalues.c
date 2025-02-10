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

// f3 notes: LASTEDIT, NOTE, 
//   11.2.2025 update date after every untested edit, delete after tested

// NOTE , test extended regex features,

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
    TOKEN_GROUP,
    TOKEN_LOOKBEHIND,
    TOKEN_LOOKAHEAD,
    TOKEN_NAMED_GROUP,
    TOKEN_NON_CAPTURING_GROUP,
    TOKEN_BACKREFERENCE,
    TOKEN_UNICODE_CATEGORY
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
    AST_GROUP,
    AST_LOOKBEHIND,
    AST_LOOKAHEAD,
    AST_NAMED_GROUP,
    AST_NON_CAPTURING_GROUP,
    AST_BACKREFERENCE,
    AST_UNICODE_CATEGORY
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

// Track named groups for backreferences
typedef struct {
    char name[256];
    char value[256];
} NamedGroup;

typedef struct {
    NamedGroup* groups;
    int num_groups;
} GroupContext;

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

char random_unicode_category(const char* category) {
    if (strcmp(category, "L") == 0 || strcmp(category, "Letter") == 0) {
        return random_char_in_range('A', 'z');
    } else if (strcmp(category, "Ll") == 0) {
        return random_lowercase();
    } else if (strcmp(category, "Lu") == 0) {
        return random_uppercase();
    } else if (strcmp(category, "N") == 0 || strcmp(category, "Number") == 0) {
        return random_digit();
    } else if (strcmp(category, "Z") == 0 || strcmp(category, "Separator") == 0) {
        return random_whitespace();
    } else if (strcmp(category, "P") == 0 || strcmp(category, "Punctuation") == 0) {
        char puncts[] = ",.;:!?()-'\"";
        return puncts[rand() % strlen(puncts)];
    } else if (strcmp(category, "S") == 0 || strcmp(category, "Symbol") == 0) {
        char symbols[] = "@#$%^&*+=<>~/\\|";
        return symbols[rand() % strlen(symbols)];
    }
    return random_char_in_range(' ', '~');
}

// seperation of regex pattern into tokens
// - 11.2.2025
// LASTEDIT special groups, alternation, lookbehind, lookahead, named groups and unicode categories
int tokenize(const char* pattern, Token** tokens, int* num_tokens) {
    *tokens = (Token*)malloc(256 * sizeof(Token));
    if (*tokens == NULL) {
        return -1;
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
            
            // unicode categories
            if (pattern[pattern_index] == 'p' || pattern[pattern_index] == 'P') {
                (*tokens)[token_index].type = TOKEN_UNICODE_CATEGORY;
                (*tokens)[token_index].is_negated = (pattern[pattern_index] == 'P');
                pattern_index++;
                if (pattern[pattern_index] == '{') {
                    pattern_index++;
                    int value_index = 0;
                    while (pattern[pattern_index] != '}') {
                        (*tokens)[token_index].value[value_index++] = pattern[pattern_index++];
                    }
                    (*tokens)[token_index].value[value_index] = '\0';
                }
                token_index++;
                pattern_index++;
            }
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
            // handle alternation, not tested yet, added 11.2.2025
            (*tokens)[token_index].type = TOKEN_ALTERNATION;
            token_index++;
            pattern_index++;
        } else if (pattern[pattern_index] == '(') {
            pattern_index++;
            // check for special group types
            if (pattern[pattern_index] == '?') {
                pattern_index++;
                if (pattern[pattern_index] == '<') {
                    pattern_index++;
                    if (pattern[pattern_index] == '=') {
                        // positive lookbehind
                        (*tokens)[token_index].type = TOKEN_LOOKBEHIND;
                        (*tokens)[token_index].is_negated = false;
                    } else if (pattern[pattern_index] == '!') {
                        // negative lookbehind
                        (*tokens)[token_index].type = TOKEN_LOOKBEHIND;
                        (*tokens)[token_index].is_negated = true;
                    } else {
                        // named capturing group
                        (*tokens)[token_index].type = TOKEN_NAMED_GROUP;
                        int name_index = 0;
                        while (pattern[pattern_index] != '>') {
                            (*tokens)[token_index].value[name_index++] = pattern[pattern_index++];
                        }
                        (*tokens)[token_index].value[name_index] = '\0';
                    }
                } else if (pattern[pattern_index] == ':') {
                    // non-capturing group
                    (*tokens)[token_index].type = TOKEN_NON_CAPTURING_GROUP;
                } else if (pattern[pattern_index] == '=') {
                    // positive lookahead
                    (*tokens)[token_index].type = TOKEN_LOOKAHEAD;
                    (*tokens)[token_index].is_negated = false;
                } else if (pattern[pattern_index] == '!') {
                    // negative lookahead
                    (*tokens)[token_index].type = TOKEN_LOOKAHEAD;
                    (*tokens)[token_index].is_negated = true;
                }
                token_index++;
            }
        } else {
            // handle literals
            (*tokens)[token_index].type = TOKEN_LITERAL;
            (*tokens)[token_index].value[0] = pattern[pattern_index];
            (*tokens)[token_index].value[1] = '\0';
            token_index++;
            pattern_index++;
        }
    }

    *num_tokens = token_index;
    return 0;
}

// function to choose random alternative
int random_choice(int n) {
    return rand() % n;
}

// helper function to parse nested groups into AST
ASTNode* parse_group(Token* tokens, int* pos, int num_tokens) {
    ASTNode* group = (ASTNode*)malloc(sizeof(ASTNode));
    if (!group) return NULL;
    
    group->type = AST_GROUP;
    // up to 32 nodes in group, expandeable
    group->children = (ASTNode*)malloc(32 * sizeof(ASTNode));
    group->num_children = 0;
    
    while (*pos < num_tokens && tokens[*pos].type != TOKEN_GROUP) {
        if (tokens[*pos].type == TOKEN_ALTERNATION) {
            (*pos)++;
            continue;
        }
        
        ASTNode node;
        node.type = (ASTNodeType)tokens[*pos].type;
        strcpy(node.value, tokens[*pos].value);
        node.min = 1;
        node.max = 1;
        node.is_negated = tokens[*pos].is_negated;
        node.children = NULL;
        node.num_children = 0;
        
        if (node.type == AST_GROUP) {
            (*pos)++;
            ASTNode* nested = parse_group(tokens, pos, num_tokens);
            if (nested) {
                node.children = nested->children;
                node.num_children = nested->num_children;
                free(nested);
            }
        }
        
        group->children[group->num_children++] = node;
        (*pos)++;
    }
    
    return group;
}

// parsing of tokens into AST, - 11.2.2025 added alternation support and other improvements
int parse_tokens(Token* tokens, int num_tokens, ASTNode** root) {
    printf("Parsing tokens...\n");
    ASTNode* nodes = (ASTNode*)malloc(num_tokens * sizeof(ASTNode));
    if (!nodes) return -1;
    
    int node_count = 0;
    for (int i = 0; i < num_tokens; ) {
        printf("Processing token %d: type=%d, value='%s'\n", i, tokens[i].type, tokens[i].value);
        
        if (tokens[i].type == TOKEN_ALTERNATION) {
            // create alternation node
            ASTNode alt_node;
            alt_node.type = AST_ALTERNATION;
            alt_node.min = 1;
            alt_node.max = 1;
            alt_node.is_negated = false;
            
            // collect all alternatives
            alt_node.children = (ASTNode*)malloc(32 * sizeof(ASTNode)); // up to 32, expandeable
            alt_node.num_children = 0;
            
            // previous token/group becomes first alternative
            if (node_count > 0) {
                if (nodes[node_count-1].type == AST_GROUP) {
                    // copy entire group as alternative
                    alt_node.children[alt_node.num_children++] = nodes[--node_count];
                } else {
                    // single token alternative
                    alt_node.children[alt_node.num_children++] = nodes[--node_count];
                }
            }
            
            // parse remaining alternatives
            i++; // skip alternation token
            while (i < num_tokens && tokens[i].type != TOKEN_GROUP) {
                if (tokens[i].type == TOKEN_ALTERNATION) {
                    i++;
                    continue;
                }
                
                if (tokens[i].type == AST_GROUP) {
                    // parse nested group
                    ASTNode* group = parse_group(tokens, &i, num_tokens);
                    if (group) {
                        alt_node.children[alt_node.num_children++] = *group;
                        free(group);
                    }
                } else {
                    // single token alternative
                    ASTNode alt = {
                        .type = (ASTNodeType)tokens[i].type,
                        .min = 1,
                        .max = 1,
                        .is_negated = tokens[i].is_negated,
                        .children = NULL,
                        .num_children = 0
                    };
                    strcpy(alt.value, tokens[i].value);
                    alt_node.children[alt_node.num_children++] = alt;
                    i++;
                }
            }
            
            // check for quantifier after alternation group
            if (i < num_tokens && tokens[i].type == TOKEN_QUANTIFIER) {
                alt_node.min = tokens[i].min;
                alt_node.max = tokens[i].max;
                i++;
            }
            
            nodes[node_count++] = alt_node;
        } else {
            // other token types
            if (tokens[i].type == TOKEN_QUANTIFIER) {
                printf("Skipping stray quantifier at index %d\n", i);
                // stray quantifier (invalid regex)
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

            // check if next token is a quantifier
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

// initialize random seed, should be called once at start of generation, 
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

    // generates data row by row, can probably be made way faster without negative impact on desired functionality
    for (int r = 0; r < rows; r++) {
        for (int h = 0; h < num_headers; h++) {
            char* buffer = (char*)malloc(256);
            if (!buffer) return -1;
            int output_index = 0;
            ASTNode* root = ast_array[h];
            // we have to walk through the AST and generate based on the encountered nodes
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
                        case AST_UNICODE_CATEGORY:
                            buffer[output_index++] = random_unicode_category(node->value);
                            break;
                        case AST_ALTERNATION: {
                            // quantified alternation
                            int repeat = (node->min == node->max) 
                                     ? node->min 
                                     : node->min + (rand() % (node->max - node->min + 1));
                            
                            for (int q = 0; q < repeat && output_index < 255; q++) {
                                // choosing random alt, number of alternatives should come from node->num_children
                                int choice = random_choice(node->num_children);
                                ASTNode* alt = &node->children[choice];
                                
                                // generate from chosen alternative
                                if (alt->type == AST_GROUP) {
                                    for (int g = 0; g < alt->num_children && output_index < 255; g++) {
                                        ASTNode* group_node = &alt->children[g];
                                        switch (group_node->type) {
                                            case AST_LITERAL:
                                                buffer[output_index++] = group_node->value[0];
                                                break;
                                            case AST_CHAR_CLASS:
                                                if (group_node->is_negated) {
                                                    char c;
                                                    do {
                                                        c = random_char_in_range(' ', '~');
                                                    } while (strchr(group_node->value, c) != NULL);
                                                    buffer[output_index++] = c;
                                                } else {
                                                    char start = group_node->value[0];
                                                    char end = group_node->value[2];
                                                    buffer[output_index++] = random_char_in_range(start, end);
                                                }
                                                break;
                                            case AST_ESCAPE:
                                                switch (group_node->value[0]) {
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
                                                        buffer[output_index++] = group_node->value[0];
                                                        break;
                                                }
                                                break;
                                            case AST_ANY_CHAR:
                                                buffer[output_index++] = random_char_in_range(' ', '~');
                                                break;
                                            case AST_UNICODE_CATEGORY:
                                                buffer[output_index++] = random_unicode_category(group_node->value);
                                                break;
                                        }
                                    }
                                } else {
                                    // non group alternatives
                                    switch (alt->type) {
                                        case AST_LITERAL:
                                            buffer[output_index++] = alt->value[0];
                                            break;
                                        case AST_CHAR_CLASS:
                                            if (alt->is_negated) {
                                                char c;
                                                do {
                                                    c = random_char_in_range(' ', '~');
                                                } while (strchr(alt->value, c) != NULL);
                                                buffer[output_index++] = c;
                                            } else {
                                                char start = alt->value[0];
                                                char end = alt->value[2];
                                                buffer[output_index++] = random_char_in_range(start, end);
                                            }
                                            break;
                                        case AST_ESCAPE:
                                            switch (alt->value[0]) {
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
                                                    buffer[output_index++] = alt->value[0];
                                                    break;
                                            }
                                            break;
                                        case AST_ANY_CHAR:
                                            buffer[output_index++] = random_char_in_range(' ', '~');
                                            break;
                                        case AST_UNICODE_CATEGORY:
                                            buffer[output_index++] = random_unicode_category(alt->value);
                                            break;
                                    }
                                }
                            }
                            break;
                        }
                        // expand with other node types, LASTEDIT 11.2.2025
                        default:
                            break;
                    }
                }
            }
            buffer[output_index] = '\0';
            (*out_data)[r*num_headers + h] = buffer;
        }
    }

    // free ASTs & tokens after generating data. 
    //      NOTE       previously freed by calling seperate function and referring to it in C, which was not ideal
    //                 as a rule, all the memory should probably be managed inside the functions where it is allocated in C
    for (int i = 0; i < num_headers; i++) {
        free_ast(ast_array[i]);
        free_tokens(token_array[i]);
    }
    free(token_array);
    free(token_counts);
    free(ast_array);

    return 0;
}

// backreference handling for generate_all_data
void handle_backreference(char* buffer, int* output_index, const GroupContext* ctx, const char* ref_name) {
    for (int i = 0; i < ctx->num_groups; i++) {
        if (strcmp(ctx->groups[i].name, ref_name) == 0) {
            strcpy(buffer + *output_index, ctx->groups[i].value);
            *output_index += strlen(ctx->groups[i].value);
            break;
        }
    }
}