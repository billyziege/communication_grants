/**
 * @generated SignedSource<<cad6c5070446bfd4b141eec4255458b3>>
 * @lightSyntaxTransform
 * @nogrep
 */

/* eslint-disable */

'use strict';

var node = (function(){
var v0 = [
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
v1 = [
  {
    "kind": "Variable",
    "name": "after",
    "variableName": "after"
  },
  {
    "kind": "Variable",
    "name": "country",
    "variableName": "country"
  },
  {
    "kind": "Variable",
    "name": "first",
    "variableName": "first"
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
];
return {
  "fragment": {
    "argumentDefinitions": (v0/*: any*/),
    "kind": "Fragment",
    "metadata": null,
    "name": "GrantListPaginationQuery",
    "selections": [
      {
        "args": (v1/*: any*/),
        "kind": "FragmentSpread",
        "name": "GrantList_query"
      }
    ],
    "type": "Query",
    "abstractKey": null
  },
  "kind": "Request",
  "operation": {
    "argumentDefinitions": (v0/*: any*/),
    "kind": "Operation",
    "name": "GrantListPaginationQuery",
    "selections": [
      {
        "alias": null,
        "args": (v1/*: any*/),
        "concreteType": "SearchGrantConnection",
        "kind": "LinkedField",
        "name": "search",
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
                    "alias": null,
                    "args": null,
                    "kind": "ScalarField",
                    "name": "title",
                    "storageKey": null
                  },
                  {
                    "alias": null,
                    "args": null,
                    "kind": "ScalarField",
                    "name": "organization",
                    "storageKey": null
                  },
                  {
                    "alias": null,
                    "args": null,
                    "kind": "ScalarField",
                    "name": "country",
                    "storageKey": null
                  },
                  {
                    "alias": null,
                    "args": null,
                    "kind": "ScalarField",
                    "name": "source",
                    "storageKey": null
                  },
                  {
                    "alias": null,
                    "args": null,
                    "kind": "ScalarField",
                    "name": "sourceId",
                    "storageKey": null
                  },
                  {
                    "alias": null,
                    "args": null,
                    "kind": "ScalarField",
                    "name": "sourceProgramme",
                    "storageKey": null
                  },
                  {
                    "alias": null,
                    "args": null,
                    "kind": "ScalarField",
                    "name": "sourceUrl",
                    "storageKey": null
                  },
                  {
                    "alias": null,
                    "args": null,
                    "kind": "ScalarField",
                    "name": "startDate",
                    "storageKey": null
                  },
                  {
                    "alias": null,
                    "args": null,
                    "kind": "ScalarField",
                    "name": "endDate",
                    "storageKey": null
                  },
                  {
                    "alias": null,
                    "args": null,
                    "kind": "ScalarField",
                    "name": "fundingAmount",
                    "storageKey": null
                  },
                  {
                    "alias": null,
                    "args": null,
                    "kind": "ScalarField",
                    "name": "fundingCurrency",
                    "storageKey": null
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
      },
      {
        "alias": null,
        "args": (v1/*: any*/),
        "filters": [
          "query",
          "source",
          "yearMin",
          "yearMax",
          "country",
          "programmes",
          "fundingMin",
          "fundingMax"
        ],
        "handle": "connection",
        "key": "GrantList_search",
        "kind": "LinkedHandle",
        "name": "search"
      }
    ]
  },
  "params": {
    "cacheID": "70dcaac4216645fe73d243a31772a9b7",
    "id": null,
    "metadata": {},
    "name": "GrantListPaginationQuery",
    "operationKind": "query",
    "text": "query GrantListPaginationQuery(\n  $after: String\n  $country: String\n  $first: Int = 100\n  $fundingMax: Float\n  $fundingMin: Float\n  $programmes: [String!]\n  $query: String!\n  $source: Source\n  $yearMax: Int\n  $yearMin: Int\n) {\n  ...GrantList_query_VqWS4\n}\n\nfragment GrantCard_grant on GrantNode {\n  id\n  title\n  organization\n  country\n  source\n  sourceId\n  sourceProgramme\n  sourceUrl\n  startDate\n  endDate\n  fundingAmount\n  fundingCurrency\n}\n\nfragment GrantList_query_VqWS4 on Query {\n  search(query: $query, source: $source, yearMin: $yearMin, yearMax: $yearMax, country: $country, programmes: $programmes, fundingMin: $fundingMin, fundingMax: $fundingMax, first: $first, after: $after) {\n    totalCount\n    edges {\n      node {\n        id\n        ...GrantCard_grant\n        __typename\n      }\n      cursor\n    }\n    pageInfo {\n      endCursor\n      hasNextPage\n    }\n  }\n}\n"
  }
};
})();

node.hash = "d13615790da400885b5f25dc56fea1c8";

export default node;
