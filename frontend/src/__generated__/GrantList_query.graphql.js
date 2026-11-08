/**
 * @generated SignedSource<<5649dec39aebff53d25eea7e45b09851>>
 * @lightSyntaxTransform
 * @nogrep
 */

/* eslint-disable */

'use strict';

import GrantListPaginationQuery_graphql from './GrantListPaginationQuery.graphql';

var node = (function(){
var v0 = [
  "search"
];
return {
  "argumentDefinitions": [
    {
      "defaultValue": null,
      "kind": "LocalArgument",
      "name": "after"
    },
    {
      "defaultValue": null,
      "kind": "LocalArgument",
      "name": "country"
    },
    {
      "defaultValue": 100,
      "kind": "LocalArgument",
      "name": "first"
    },
    {
      "defaultValue": null,
      "kind": "LocalArgument",
      "name": "fundingMax"
    },
    {
      "defaultValue": null,
      "kind": "LocalArgument",
      "name": "fundingMin"
    },
    {
      "defaultValue": null,
      "kind": "LocalArgument",
      "name": "programmes"
    },
    {
      "defaultValue": null,
      "kind": "LocalArgument",
      "name": "query"
    },
    {
      "defaultValue": null,
      "kind": "LocalArgument",
      "name": "source"
    },
    {
      "defaultValue": null,
      "kind": "LocalArgument",
      "name": "yearMax"
    },
    {
      "defaultValue": null,
      "kind": "LocalArgument",
      "name": "yearMin"
    }
  ],
  "kind": "Fragment",
  "metadata": {
    "connection": [
      {
        "count": "first",
        "cursor": "after",
        "direction": "forward",
        "path": (v0/*: any*/)
      }
    ],
    "refetch": {
      "connection": {
        "forward": {
          "count": "first",
          "cursor": "after"
        },
        "backward": null,
        "path": (v0/*: any*/)
      },
      "fragmentPathInResult": [],
      "operation": GrantListPaginationQuery_graphql
    }
  },
  "name": "GrantList_query",
  "selections": [
    {
      "alias": "search",
      "args": [
        {
          "kind": "Variable",
          "name": "country",
          "variableName": "country"
        },
        {
          "kind": "Variable",
          "name": "fundingMax",
          "variableName": "fundingMax"
        },
        {
          "kind": "Variable",
          "name": "fundingMin",
          "variableName": "fundingMin"
        },
        {
          "kind": "Variable",
          "name": "programmes",
          "variableName": "programmes"
        },
        {
          "kind": "Variable",
          "name": "query",
          "variableName": "query"
        },
        {
          "kind": "Variable",
          "name": "source",
          "variableName": "source"
        },
        {
          "kind": "Variable",
          "name": "yearMax",
          "variableName": "yearMax"
        },
        {
          "kind": "Variable",
          "name": "yearMin",
          "variableName": "yearMin"
        }
      ],
      "concreteType": "SearchGrantConnection",
      "kind": "LinkedField",
      "name": "__GrantList_search_connection",
      "plural": false,
      "selections": [
        {
          "alias": null,
          "args": null,
          "kind": "ScalarField",
          "name": "totalCount",
          "storageKey": null
        },
        {
          "alias": null,
          "args": null,
          "concreteType": "GrantNodeEdge",
          "kind": "LinkedField",
          "name": "edges",
          "plural": true,
          "selections": [
            {
              "alias": null,
              "args": null,
              "concreteType": "GrantNode",
              "kind": "LinkedField",
              "name": "node",
              "plural": false,
              "selections": [
                {
                  "alias": null,
                  "args": null,
                  "kind": "ScalarField",
                  "name": "id",
                  "storageKey": null
                },
                {
                  "args": null,
                  "kind": "FragmentSpread",
                  "name": "GrantCard_grant"
                },
                {
                  "alias": null,
                  "args": null,
                  "kind": "ScalarField",
                  "name": "__typename",
                  "storageKey": null
                }
              ],
              "storageKey": null
            },
            {
              "alias": null,
              "args": null,
              "kind": "ScalarField",
              "name": "cursor",
              "storageKey": null
            }
          ],
          "storageKey": null
        },
        {
          "alias": null,
          "args": null,
          "concreteType": "PageInfo",
          "kind": "LinkedField",
          "name": "pageInfo",
          "plural": false,
          "selections": [
            {
              "alias": null,
              "args": null,
              "kind": "ScalarField",
              "name": "endCursor",
              "storageKey": null
            },
            {
              "alias": null,
              "args": null,
              "kind": "ScalarField",
              "name": "hasNextPage",
              "storageKey": null
            }
          ],
          "storageKey": null
        }
      ],
      "storageKey": null
    }
  ],
  "type": "Query",
  "abstractKey": null
};
})();

node.hash = "d13615790da400885b5f25dc56fea1c8";

export default node;
